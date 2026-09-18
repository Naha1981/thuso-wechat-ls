from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import SecretCipher
from app.core.config import get_settings
from app.core.db import get_db
from app.services.partner_integrations import (
    SECRET_FIELDS,
    hash_token,
    test_partner,
    discover_openapi,
    validate_endpoint,
    normalise_path,
    _build,
)

router = APIRouter(prefix="/partner", tags=["partner-onboarding"])


class IntegrationIn(BaseModel):
    provider_key: str = Field(min_length=3, max_length=120)
    base_url: str = Field(min_length=8, max_length=2000)
    adapter_type: str = "rest_json"
    api_spec_url: str | None = None
    health_endpoint_path: str | None = "/health"
    auth_scheme: str = "bearer"
    auth_header_name: str = "Authorization"
    auth_config: dict = Field(default_factory=dict)
    timeout_seconds: int = Field(default=30, ge=5, le=180)
    api_key: str | None = Field(default=None, max_length=10000)
    api_secret: str | None = Field(default=None, max_length=10000)
    hmac_secret: str | None = Field(default=None, max_length=10000)
    client_secret: str | None = Field(default=None, max_length=10000)
    client_cert_pem: str | None = Field(default=None, max_length=50000)
    client_key_pem: str | None = Field(default=None, max_length=50000)
    ca_bundle_pem: str | None = Field(default=None, max_length=50000)
    extra_headers: dict[str, str] | None = None
    allow_private_network: bool = False
    request_defaults: dict = Field(default_factory=dict)
    operation_configs: dict = Field(default_factory=dict)
    response_mappings: dict = Field(default_factory=dict)
    webhook_config: dict = Field(default_factory=dict)
    workflow_configs: dict = Field(default_factory=dict)


class TestRequest(BaseModel):
    operation: str | None = None


def _token(value: str | None) -> str:
    if not value:
        raise HTTPException(401, "Onboarding token is required")
    return hash_token(value)


async def _invite(db: AsyncSession, token: str):
    row = (
        await db.execute(
            text("""
                select id, stakeholder_name, stakeholder_type, service_domain,
                       expires_at, consumed_at, integration_id
                from partner_invites
                where token_hash=:token_hash
                limit 1
            """),
            {"token_hash": _token(token)},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(401, "Invalid onboarding token")
    if row["consumed_at"] is not None:
        raise HTTPException(410, "Onboarding link has already been used")
    if row["expires_at"] <= datetime.now(UTC):
        raise HTTPException(410, "Onboarding link has expired")
    return row


async def _saved(db: AsyncSession, invite_id: str):
    row = (
        await db.execute(
            text("""
                select id, stakeholder_name, stakeholder_type, service_domain,
                       provider_key, environment, enabled, allow_private_network, adapter_type, base_url, api_spec_url,
                       health_endpoint_path, auth_scheme, auth_header_name, auth_config,
                       timeout_seconds, request_defaults, operation_configs,
                       response_mappings, webhook_config, workflow_configs, secret_ciphertext,
                       last_test_status, last_test_operation
                from partner_integrations
                where partner_invite_id=:invite_id
                limit 1
            """),
            {"invite_id": invite_id},
        )
    ).mappings().first()
    if not row:
        return None, {}
    secrets_map = {}
    if row["secret_ciphertext"]:
        secrets_map = json.loads(SecretCipher(get_settings().secrets_encryption_key).decrypt(row["secret_ciphertext"]))
    return _build(dict(row), secrets_map), secrets_map


def _public(config, secrets_map):
    if not config:
        return {"configured": False, "enabled": False, "secret_configured": False}
    return {
        "configured": True,
        "stakeholder_name": config.stakeholder_name,
        "stakeholder_type": config.stakeholder_type,
        "service_domain": config.service_domain,
        "provider_key": config.provider_key,
        "environment": config.environment,
        "enabled": config.enabled,
        "base_url": config.base_url,
        "adapter_type": config.adapter_type,
        "allow_private_network": config.allow_private_network,
        "api_spec_url": config.api_spec_url,
        "health_endpoint_path": config.health_endpoint_path,
        "auth_scheme": config.auth_scheme,
        "auth_config": config.auth_config,
        "timeout_seconds": config.timeout_seconds,
        "request_defaults": config.request_defaults,
        "operation_configs": config.operation_configs,
        "response_mappings": config.response_mappings,
        "webhook_config": config.webhook_config,
        "workflow_configs": config.workflow_configs,
        "secret_configured": bool(secrets_map),
        "last_test_status": config.last_test_status,
        "last_test_operation": config.last_test_operation,
    }


@router.post("/status")
async def status(body: dict, x_nahaos_onboarding_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    invite = await _invite(db, x_nahaos_onboarding_token)
    config, secrets_map = await _saved(db, str(invite["id"]))
    return {"invite": {
        "stakeholder_name": invite["stakeholder_name"],
        "stakeholder_type": invite["stakeholder_type"],
        "service_domain": invite["service_domain"],
        "expires_at": invite["expires_at"],
    }, "integration": _public(config, secrets_map)}


@router.put("/integration")
async def save(
    body: IntegrationIn,
    x_nahaos_onboarding_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    invite = await _invite(db, x_nahaos_onboarding_token)
    if body.adapter_type not in {"rest_json", "graphql", "form_urlencoded", "soap_xml"}:
        raise HTTPException(422, "Unsupported adapter type")
    if body.auth_scheme not in {"bearer", "api-key", "basic", "custom", "none", "oauth2_client_credentials", "hmac_sha256", "mtls"}:
        raise HTTPException(422, "Unsupported auth scheme")
    validate_endpoint(body.base_url, body.allow_private_network)
    normalise_path(body.health_endpoint_path, None)
    try:
        json.dumps(body.request_defaults)
        json.dumps(body.operation_configs)
        json.dumps(body.response_mappings)
    except TypeError as exc:
        raise HTTPException(422, "Integration mapping must be valid JSON") from exc

    current, current_secrets = await _saved(db, str(invite["id"]))
    secrets_map = dict(current_secrets)
    for field in SECRET_FIELDS:
        value = getattr(body, field)
        if value not in (None, ""):
            secrets_map[field] = value
    if body.auth_scheme != "custom":
        secrets_map.pop("extra_headers", None)
    if body.auth_scheme == "none":
        for key in ("api_key", "api_secret", "hmac_secret", "client_secret", "client_cert_pem", "client_key_pem", "ca_bundle_pem"):
            secrets_map.pop(key, None)
    if body.auth_scheme in {"bearer", "api-key"}:
        secrets_map.pop("api_secret", None)
        secrets_map.pop("hmac_secret", None)
        secrets_map.pop("client_secret", None)
        secrets_map.pop("client_cert_pem", None)
        secrets_map.pop("client_key_pem", None)
        secrets_map.pop("ca_bundle_pem", None)
    if body.auth_scheme == "hmac_sha256":
        secrets_map.pop("api_key", None)
        secrets_map.pop("api_secret", None)
        secrets_map.pop("client_secret", None)
    if body.auth_scheme == "oauth2_client_credentials":
        secrets_map.pop("api_key", None)
        secrets_map.pop("api_secret", None)
        secrets_map.pop("hmac_secret", None)
    if body.auth_scheme == "mtls":
        secrets_map.pop("api_key", None)
        secrets_map.pop("api_secret", None)
        secrets_map.pop("hmac_secret", None)
        secrets_map.pop("client_secret", None)

    ciphertext = SecretCipher(get_settings().secrets_encryption_key).encrypt(
        json.dumps(secrets_map, separators=(",", ":"))
    ) if secrets_map else None

    values = {
        "provider_key": body.provider_key,
        "base_url": body.base_url.rstrip("/"),
        "adapter_type": body.adapter_type,
        "api_spec_url": body.api_spec_url,
        "health_endpoint_path": normalise_path(body.health_endpoint_path, None),
        "auth_scheme": body.auth_scheme,
        "auth_header_name": body.auth_header_name,
        "auth_config": json.dumps(body.auth_config),
        "timeout_seconds": body.timeout_seconds,
        "allow_private_network": body.allow_private_network,
        "webhook_config": json.dumps(body.webhook_config),
        "workflow_configs": json.dumps(body.workflow_configs),
        "request_defaults": json.dumps(body.request_defaults),
        "operation_configs": json.dumps(body.operation_configs),
        "response_mappings": json.dumps(body.response_mappings),
        "secret_ciphertext": ciphertext,
    }

    if current and current.provider_key != body.provider_key:
        exists = await db.execute(text("select 1 from partner_integrations where provider_key=:key and id<>:id limit 1"), {"key": body.provider_key, "id": current.id})
        if exists.first():
            raise HTTPException(409, "Provider key is already in use")

    if current:
        await db.execute(text("""
            update partner_integrations set
              provider_key=:provider_key, adapter_type=:adapter_type, enabled=false, base_url=:base_url,
              api_spec_url=:api_spec_url, health_endpoint_path=:health_endpoint_path,
              auth_scheme=:auth_scheme, auth_header_name=:auth_header_name,
              auth_config=cast(:auth_config as jsonb),
              timeout_seconds=:timeout_seconds, allow_private_network=:allow_private_network,
              request_defaults=cast(:request_defaults as jsonb),
              operation_configs=cast(:operation_configs as jsonb),
              response_mappings=cast(:response_mappings as jsonb),
              webhook_config=cast(:webhook_config as jsonb),
              workflow_configs=cast(:workflow_configs as jsonb),
              secret_ciphertext=:secret_ciphertext, last_test_at=null,
              last_test_status=null, last_test_operation=null, last_test_error=null,
              version=version+1, updated_at=now()
            where id=:id
        """), {"id": current.id, **values})
        integration_id = current.id
    else:
        integration_id = (
            await db.execute(text("""
                insert into partner_integrations(
                  partner_invite_id, stakeholder_name, stakeholder_type, service_domain,
                  provider_key, adapter_type, environment, enabled, base_url, api_spec_url,
                  health_endpoint_path, allow_private_network, auth_scheme, auth_header_name, auth_config, timeout_seconds,
                  request_defaults, operation_configs, response_mappings, webhook_config, workflow_configs, secret_ciphertext
                ) values (
                  :invite_id, :name, :type, :domain, :provider_key, :adapter_type, 'production', false,
                  :base_url, :api_spec_url, :health_endpoint_path, :allow_private_network, :auth_scheme,
                  :auth_header_name, cast(:auth_config as jsonb), :timeout_seconds, cast(:request_defaults as jsonb),
                  cast(:operation_configs as jsonb), cast(:response_mappings as jsonb),
                  cast(:webhook_config as jsonb), cast(:workflow_configs as jsonb),
                  :secret_ciphertext
                ) returning id
            """), {
                "invite_id": invite["id"],
                "name": invite["stakeholder_name"],
                "type": invite["stakeholder_type"],
                "domain": invite["service_domain"],
                **values,
            })
        ).scalar_one()
        await db.execute(text("update partner_invites set integration_id=:id where id=:invite_id"), {"id": integration_id, "invite_id": invite["id"]})
    await db.commit()
    config, secrets_map = await _saved(db, str(invite["id"]))
    return _public(config, secrets_map)


class DiscoverIn(BaseModel):
    openapi_url: str = Field(min_length=8, max_length=2000)


@router.post("/discover")
async def discover(
    body: DiscoverIn,
    x_nahaos_onboarding_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    await _invite(db, x_nahaos_onboarding_token)
    try:
        return await discover_openapi(body.openapi_url)
    except Exception as exc:
        raise HTTPException(422, "Could not read the OpenAPI document") from exc


@router.post("/integration/test")
async def test(
    body: TestRequest,
    x_nahaos_onboarding_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    invite = await _invite(db, x_nahaos_onboarding_token)
    config, _ = await _saved(db, str(invite["id"]))
    if not config:
        raise HTTPException(404, "Integration has not been configured")
    try:
        result = await test_partner(config, operation=body.operation)
        await db.execute(text("""
            update partner_integrations
            set last_test_at=now(), last_test_status='passed', last_test_operation=:operation,
                last_test_error=null
            where id=:id
        """), {"id": config.id, "operation": result["kind"]})
        await db.commit()
        return result
    except Exception as exc:
        await db.execute(text("""
            update partner_integrations
            set last_test_at=now(), last_test_status='failed', last_test_operation=:operation,
                last_test_error=:error
            where id=:id
        """), {"id": config.id, "operation": body.operation or "health", "error": str(exc)[:500]})
        await db.commit()
        raise HTTPException(502, "Partner integration test failed") from exc


@router.post("/integration/activate")
async def activate(
    x_nahaos_onboarding_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    invite = await _invite(db, x_nahaos_onboarding_token)
    config, _ = await _saved(db, str(invite["id"]))
    if not config:
        raise HTTPException(404, "Integration has not been configured")
    if config.last_test_status != "passed" or config.last_test_operation in {None, "health"}:
        raise HTTPException(409, "Run and pass at least one service operation test before activation")
    await db.execute(text("update partner_integrations set enabled=false where service_domain=:domain and environment='production'"), {"domain": config.service_domain})
    await db.execute(text("update partner_integrations set enabled=true,updated_at=now() where id=:id"), {"id": config.id})
    await db.execute(text("update partner_invites set consumed_at=now() where id=:id"), {"id": invite["id"]})
    await db.commit()
    return {"ok": True, "active_provider": config.provider_key, "service_domain": config.service_domain}
