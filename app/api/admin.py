from __future__ import annotations

from datetime import datetime, timezone
import hmac
import json

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_auth import (
    create_admin_session,
    hash_admin_password,
    require_admin,
    require_admin_write,
    verify_admin_password,
    session_cookie_settings,
)
from app.core.config import get_settings
from app.core.db import get_db
from app.services.econet_integration import (
    get_saved_econet_config,
    save_econet_config,
    test_econet_config,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class BootstrapIn(BaseModel):
    bootstrap_token: str = Field(min_length=1, max_length=500)
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=12, max_length=256)


class LoginIn(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class EconetConfigIn(BaseModel):
    base_url: str
    chat_endpoint_path: str = "/chat/completions"
    health_endpoint_path: str | None = "/health"
    auth_scheme: str = "bearer"
    auth_header_name: str = "Authorization"
    model: str = "default"
    timeout_seconds: int = Field(default=60, ge=5, le=180)
    api_key: str | None = Field(default=None, max_length=10000)
    api_secret: str | None = Field(default=None, max_length=10000)
    extra_headers: dict[str, str] | None = None
    allow_private_network: bool = False
    request_template: dict = Field(default_factory=dict)
    response_mapping: dict = Field(default_factory=dict)


class TestIn(BaseModel):
    smoke_chat: bool = False


def _normalise_email(email: str) -> str:
    try:
        return validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise HTTPException(422, str(exc)) from exc


def _cookie(response: Response, name: str, value: str, max_age: int, *, httponly: bool) -> None:
    secure, samesite = session_cookie_settings()
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=httponly,
        secure=secure,
        samesite=samesite,
        path="/",
    )


async def _audit(
    db: AsyncSession,
    admin_id: str,
    action: str,
    target_type: str,
    target_id: str | None,
    metadata: dict,
):
    await db.execute(
        text(
            """
            insert into admin_audit_events(admin_user_id, action, target_type, target_id, metadata)
            values(:admin_id, :action, :target_type, :target_id, cast(:metadata as jsonb))
            """
        ),
        {
            "admin_id": admin_id,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "metadata": json.dumps(metadata),
        },
    )


def _public_config(config, secrets: dict) -> dict:
    if not config:
        return {"configured": False, "enabled": False, "secret_configured": False}
    return {
        "configured": True,
        "id": config.id,
        "environment": config.environment,
        "enabled": config.enabled,
        "allow_private_network": config.allow_private_network,
        "base_url": config.base_url,
        "chat_endpoint_path": config.chat_endpoint_path,
        "health_endpoint_path": config.health_endpoint_path,
        "auth_scheme": config.auth_scheme,
        "auth_header_name": config.auth_header_name,
        "model": config.model,
        "timeout_seconds": config.timeout_seconds,
        "request_template": config.request_template,
        "response_mapping": config.response_mapping,
        "secret_configured": bool(secrets),
        "last_test_at": config.last_test_at,
        "last_test_status": config.last_test_status,
    }


def _login_response(response: Response, token: str, csrf: str, expires_at):
    settings = get_settings()
    _cookie(
        response,
        settings.admin_cookie_name,
        token,
        settings.admin_session_ttl_hours * 3600,
        httponly=True,
    )
    _cookie(
        response,
        settings.admin_csrf_cookie_name,
        csrf,
        settings.admin_session_ttl_hours * 3600,
        httponly=False,
    )
    return {"ok": True, "expires_at": expires_at}


@router.post("/auth/bootstrap")
async def bootstrap(
    body: BootstrapIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    if not settings.admin_bootstrap_token:
        raise HTTPException(503, "Admin bootstrap is disabled")
    if not hmac.compare_digest(body.bootstrap_token, settings.admin_bootstrap_token):
        raise HTTPException(401, "Invalid bootstrap token")

    count = (await db.execute(text("select count(*) from admin_users"))).scalar_one()
    if count:
        raise HTTPException(409, "Admin bootstrap has already been completed")

    email = _normalise_email(body.email)
    password_hash = hash_admin_password(body.password)
    admin_id = (
        await db.execute(
            text("insert into admin_users(email,password_hash) values(:email,:hash) returning id"),
            {"email": email, "hash": password_hash},
        )
    ).scalar_one()
    await _audit(db, str(admin_id), "admin.bootstrap", "admin_user", str(admin_id), {"email": email})
    token, csrf, expires = await create_admin_session(
        db, admin_user_id=str(admin_id), request=request
    )
    await db.commit()
    return _login_response(response, token, csrf, expires)


@router.post("/auth/login")
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    email = _normalise_email(body.email)
    row = (
        await db.execute(
            text(
                """
                select id, email, password_hash, role, status, failed_login_attempts, locked_until
                from admin_users where email=:email limit 1
                """
            ),
            {"email": email},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(401, "Invalid credentials")

    now = datetime.now(timezone.utc)
    if row["locked_until"] and row["locked_until"] > now:
        raise HTTPException(423, "Admin account temporarily locked")

    if not verify_admin_password(body.password, row["password_hash"]):
        attempts = int(row["failed_login_attempts"]) + 1
        if attempts >= 5:
            await db.execute(
                text(
                    """
                    update admin_users
                    set failed_login_attempts=0,
                        locked_until=now() + interval '15 minutes'
                    where id=:id
                    """
                ),
                {"id": row["id"]},
            )
        else:
            await db.execute(
                text("update admin_users set failed_login_attempts=:attempts where id=:id"),
                {"attempts": attempts, "id": row["id"]},
            )
        await db.commit()
        raise HTTPException(401, "Invalid credentials")

    await db.execute(
        text(
            """
            update admin_users
            set failed_login_attempts=0, locked_until=null, last_login_at=now()
            where id=:id
            """
        ),
        {"id": row["id"]},
    )
    token, csrf, expires = await create_admin_session(
        db, admin_user_id=str(row["id"]), request=request
    )
    await _audit(db, str(row["id"]), "admin.login", "admin_user", str(row["id"]), {})
    await db.commit()
    return _login_response(response, token, csrf, expires)


@router.post("/auth/logout")
async def logout(
    response: Response,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(text("update admin_sessions set revoked_at=now() where id=:id"), {"id": admin["id"]})
    await db.commit()
    settings = get_settings()
    response.delete_cookie(settings.admin_cookie_name, path="/")
    response.delete_cookie(settings.admin_csrf_cookie_name, path="/")
    return {"ok": True}


@router.get("/auth/me")
async def me(admin=Depends(require_admin)):
    return {
        "email": admin["email"],
        "role": admin["role"],
        "expires_at": admin["expires_at"],
    }


@router.get("/integrations/econet")
async def get_econet(admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    config, secrets = await get_saved_econet_config(db)
    return _public_config(config, secrets)


@router.put("/integrations/econet")
async def put_econet(
    body: EconetConfigIn,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    if body.auth_scheme not in {"bearer", "api-key", "basic", "custom", "none"}:
        raise HTTPException(422, "Unsupported auth scheme")
    try:
        result = await save_econet_config(
            db, admin_id=str(admin["admin_user_id"]), payload=body.model_dump()
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(422, str(exc)) from exc
    await _audit(
        db,
        str(admin["admin_user_id"]),
        "integration.save",
        "integration",
        result["id"],
        {"provider": "econet-ai", "environment": "production"},
    )
    await db.commit()
    return result


@router.post("/integrations/econet/test")
async def test_econet(
    body: TestIn,
    admin=Depends(require_admin_write),
    db: AsyncSession = Depends(get_db),
):
    config, _ = await get_saved_econet_config(db)
    if not config:
        raise HTTPException(404, "Econet integration has not been configured")

    try:
        result = await test_econet_config(config, smoke_chat=body.smoke_chat)
        await db.execute(
            text(
                "update integration_configs set last_test_at=now(), last_test_status='passed', last_test_error=null where id=:id"
            ),
            {"id": config.id},
        )
        await _audit(
            db,
            str(admin["admin_user_id"]),
            "integration.test",
            "integration",
            config.id,
            {"provider": "econet-ai", "kind": result["kind"]},
        )
        await db.commit()
        return result
    except Exception as exc:
        await db.execute(
            text(
                "update integration_configs set last_test_at=now(), last_test_status='failed', last_test_error=:error where id=:id"
            ),
            {"id": config.id, "error": str(exc)[:500]},
        )
        await db.commit()
        raise HTTPException(502, "Econet integration test failed") from exc


@router.post("/integrations/econet/activate")
async def activate_econet(admin=Depends(require_admin_write), db: AsyncSession = Depends(get_db)):
    config, _ = await get_saved_econet_config(db)
    if not config:
        raise HTTPException(404, "Econet integration has not been configured")
    if config.last_test_status != "passed":
        raise HTTPException(409, "Run and pass a connectivity test before activation")

    await db.execute(
        text(
            """
            update integration_configs
            set enabled=false, updated_at=now(), updated_by=:admin_id
            where provider='econet-ai' and environment='production'
            """
        ),
        {"admin_id": admin["admin_user_id"]},
    )
    await db.execute(
        text(
            """
            update integration_configs
            set enabled=true, updated_at=now(), updated_by=:admin_id
            where id=:id
            """
        ),
        {"id": config.id, "admin_id": admin["admin_user_id"]},
    )
    await _audit(
        db, str(admin["admin_user_id"]), "integration.activate", "integration",
        config.id, {"provider": "econet-ai"}
    )
    await db.commit()
    return {"ok": True, "active_provider": "econet-ai"}


@router.post("/integrations/econet/deactivate")
async def deactivate_econet(admin=Depends(require_admin_write), db: AsyncSession = Depends(get_db)):
    config, _ = await get_saved_econet_config(db)
    if not config:
        return {"ok": True, "active_provider": "demo"}
    await db.execute(
        text(
            """
            update integration_configs
            set enabled=false, updated_at=now(), updated_by=:admin_id
            where id=:id
            """
        ),
        {"id": config.id, "admin_id": admin["admin_user_id"]},
    )
    await _audit(
        db, str(admin["admin_user_id"]), "integration.deactivate", "integration",
        config.id, {"provider": "econet-ai"}
    )
    await db.commit()
    return {"ok": True, "active_provider": "demo"}


@router.get("/audit")
async def audit(limit: int = 50, admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    limit = max(1, min(limit, 200))
    rows = (
        await db.execute(
            text(
                """
                select id, action, target_type, target_id, metadata, created_at
                from admin_audit_events
                order by created_at desc
                limit :limit
                """
            ),
            {"limit": limit},
        )
    ).mappings().all()
    return {"events": [dict(row) for row in rows]}
