from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db

PASSWORD_N = 32768
PASSWORD_R = 8
PASSWORD_P = 1
PASSWORD_LEN = 64


def _password_hash(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=PASSWORD_N,
        r=PASSWORD_R,
        p=PASSWORD_P,
        dklen=PASSWORD_LEN,
    )
    return "$".join(
        [
            "scrypt",
            str(PASSWORD_N),
            str(PASSWORD_R),
            str(PASSWORD_P),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def _password_verify(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_b64, digest_b64 = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.urlsafe_b64decode(salt_b64.encode("ascii")),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(base64.urlsafe_b64decode(digest_b64.encode("ascii"))),
        )
        return hmac.compare_digest(
            digest,
            base64.urlsafe_b64decode(digest_b64.encode("ascii")),
        )
    except Exception:
        return False


def hash_admin_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Admin passwords must be at least 12 characters")
    return _password_hash(password)


def verify_admin_password(password: str, encoded: str) -> bool:
    return _password_verify(password, encoded)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_admin_session(
    db: AsyncSession,
    *,
    admin_user_id: str,
    request: Request,
) -> tuple[str, str, datetime]:
    settings = get_settings()
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.admin_session_ttl_hours)

    await db.execute(
        text(
            """
            insert into admin_sessions
              (admin_user_id, token_hash, csrf_hash, expires_at, ip_address, user_agent)
            values
              (:uid, :token_hash, :csrf_hash, :expires_at, cast(:ip as inet), :user_agent)
            """
        ),
        {
            "uid": admin_user_id,
            "token_hash": _hash_token(token),
            "csrf_hash": _hash_token(csrf),
            "expires_at": expires,
            "ip": request.client.host if request.client else None,
            "user_agent": (request.headers.get("user-agent") or "")[:1000],
        },
    )
    return token, csrf, expires


async def resolve_admin_session(
    db: AsyncSession,
    token: str,
) -> dict | None:
    row = (
        await db.execute(
            text(
                """
                select s.id, s.admin_user_id, s.csrf_hash, s.expires_at,
                       u.email, u.role, u.status
                from admin_sessions s
                join admin_users u on u.id = s.admin_user_id
                where s.token_hash=:token_hash
                  and s.revoked_at is null
                  and s.expires_at > now()
                limit 1
                """
            ),
            {"token_hash": _hash_token(token)},
        )
    ).mappings().first()
    if not row or row["status"] != "active":
        return None
    await db.execute(
        text("update admin_sessions set last_seen_at=now() where id=:id"),
        {"id": row["id"]},
    )
    return dict(row)


def session_cookie_settings() -> tuple[bool, str]:
    settings = get_settings()
    secure = settings.admin_cookie_secure or settings.app_env.lower() in {"prod", "production"}
    return secure, settings.admin_cookie_samesite


async def require_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = get_settings()
    token = request.cookies.get(settings.admin_cookie_name)
    if not token:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(401, "Admin authentication required")

    session = await resolve_admin_session(db, token)
    if not session:
        raise HTTPException(401, "Admin session expired or invalid")

    session["_token"] = token
    return session


async def require_admin_write(
    request: Request,
    admin=Depends(require_admin),
) -> dict:
    settings = get_settings()
    csrf_cookie = request.cookies.get(settings.admin_csrf_cookie_name)
    csrf_header = request.headers.get("x-csrf-token")
    if (not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header)
            or not hmac.compare_digest(_hash_token(csrf_header), admin["csrf_hash"])):
        raise HTTPException(403, "CSRF validation failed")
    return admin
