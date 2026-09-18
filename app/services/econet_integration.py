from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import os
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import SecretCipher

DEFAULT_REQUEST_TEMPLATE = {
    "model": "{{model}}",
    "messages": "{{messages}}",
    "metadata": "{{metadata}}",
}
DEFAULT_RESPONSE_MAPPING = {
    "content_path": "choices.0.message.content",
    "model_path": "model",
    "input_units_path": "usage.prompt_tokens",
    "output_units_path": "usage.completion_tokens",
}
SECRET_FIELDS = {"api_key", "api_secret", "extra_headers"}


@dataclass(frozen=True)
class EconetIntegration:
    id: str
    environment: str
    enabled: bool
    allow_private_network: bool
    base_url: str
    chat_endpoint_path: str
    health_endpoint_path: str | None
    auth_scheme: str
    auth_header_name: str
    model: str
    timeout_seconds: int
    request_template: dict[str, Any]
    response_mapping: dict[str, Any]
    secrets: dict[str, Any]
    last_test_status: str | None
    last_test_kind: str | None
    last_test_at: str | None


def _json_path(value: Any, path: str | None) -> Any:
    if not path:
        return None
    current = value
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(path)
    return current


def _render_template(node: Any, variables: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        return {key: _render_template(value, variables) for key, value in node.items()}
    if isinstance(node, list):
        return [_render_template(value, variables) for value in node]
    if isinstance(node, str):
        if node.startswith("{{") and node.endswith("}}") and node.count("{{") == 1:
            key = node[2:-2].strip()
            if key in variables:
                return variables[key]
        rendered = node
        for key, value in variables.items():
            rendered = rendered.replace("{{" + key + "}}", str(value))
        return rendered
    return node


def _validate_endpoint(base_url: str, allow_private_network: bool = False) -> None:
    parsed = httpx.URL(base_url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("Econet base URL must use HTTP or HTTPS")
    if not parsed.host:
        raise ValueError("Econet base URL must include a hostname")
    if parsed.scheme == "http" and os.getenv("APP_ENV", "development").lower() in {"prod", "production"}:
        raise ValueError("Production Econet endpoints must use HTTPS")
    if allow_private_network:
        return
    try:
        addresses = socket.getaddrinfo(
            parsed.host,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError("Econet hostname could not be resolved") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("Econet endpoint resolves to a private/reserved network")


def _normalise_path(path: str, default: str) -> str:
    value = (path or default).strip()
    if not value.startswith("/") or ".." in value:
        raise ValueError("Endpoint paths must be absolute paths without '..'")
    return value


def _auth_headers(config: EconetIntegration) -> dict[str, str]:
    secrets_map = config.secrets
    scheme = config.auth_scheme.lower()
    if scheme == "none":
        return {}
    if scheme == "bearer":
        key = secrets_map.get("api_key")
        if not key:
            raise RuntimeError("Econet API key is missing")
        return {"Authorization": f"Bearer {key}"}
    if scheme == "api-key":
        key = secrets_map.get("api_key")
        if not key:
            raise RuntimeError("Econet API key is missing")
        return {config.auth_header_name: str(key)}
    if scheme == "basic":
        import base64
        username = secrets_map.get("api_key")
        password = secrets_map.get("api_secret")
        if not username or password is None:
            raise RuntimeError("Econet basic-auth credentials are missing")
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    if scheme == "custom":
        headers = secrets_map.get("extra_headers") or {}
        if not isinstance(headers, dict):
            raise RuntimeError("Custom headers are invalid")
        return {str(k): str(v) for k, v in headers.items()}
    raise RuntimeError(f"Unsupported Econet auth scheme: {config.auth_scheme}")


def _safe_http_error(response: httpx.Response) -> RuntimeError:
    return RuntimeError(f"Econet AI returned HTTP {response.status_code}")


def build_econet_config(row: dict, secrets: dict[str, Any]) -> EconetIntegration:
    return EconetIntegration(
        id=str(row["id"]),
        environment=row["environment"],
        enabled=bool(row["enabled"]),
        allow_private_network=bool(row.get("allow_private_network", False)),
        base_url=row["base_url"].rstrip("/"),
        chat_endpoint_path=_normalise_path(row["chat_endpoint_path"], "/chat/completions"),
        health_endpoint_path=_normalise_path(row["health_endpoint_path"], "/health")
        if row.get("health_endpoint_path") else None,
        auth_scheme=row["auth_scheme"],
        auth_header_name=row["auth_header_name"],
        model=row["model"],
        timeout_seconds=max(5, min(int(row["timeout_seconds"]), 180)),
        request_template=row.get("request_template") or DEFAULT_REQUEST_TEMPLATE,
        response_mapping=row.get("response_mapping") or DEFAULT_RESPONSE_MAPPING,
        secrets=secrets,
        last_test_status=row.get("last_test_status"),
        last_test_kind=row.get("last_test_kind"),
        last_test_at=str(row["last_test_at"]) if row.get("last_test_at") else None,
    )


async def _load_saved_row(db: AsyncSession):
    return (
        await db.execute(
            text(
                """
                select id, environment, enabled, allow_private_network, base_url,
                       chat_endpoint_path, health_endpoint_path, auth_scheme,
                       auth_header_name, model, timeout_seconds, request_template,
                       response_mapping, secret_ciphertext, last_test_status, last_test_kind, last_test_at
                from integration_configs
                where provider='econet-ai' and environment='production'
                limit 1
                """
            )
        )
    ).mappings().first()


async def load_active_econet_config(db: AsyncSession) -> EconetIntegration | None:
    row = (
        await db.execute(
            text(
                """
                select id, environment, enabled, allow_private_network, base_url,
                       chat_endpoint_path, health_endpoint_path, auth_scheme,
                       auth_header_name, model, timeout_seconds, request_template,
                       response_mapping, secret_ciphertext, last_test_status, last_test_at
                from integration_configs
                where provider='econet-ai' and environment='production' and enabled=true
                limit 1
                """
            )
        )
    ).mappings().first()
    if not row:
        return None
    secrets = {}
    if row["secret_ciphertext"]:
        secrets = json.loads(
            SecretCipher(get_settings().secrets_encryption_key).decrypt(row["secret_ciphertext"])
        )
    return build_econet_config(dict(row), secrets)


async def get_saved_econet_config(db: AsyncSession) -> tuple[EconetIntegration | None, dict[str, Any]]:
    row = await _load_saved_row(db)
    if not row:
        return None, {}
    secrets = {}
    if row["secret_ciphertext"]:
        secrets = json.loads(
            SecretCipher(get_settings().secrets_encryption_key).decrypt(row["secret_ciphertext"])
        )
    return build_econet_config(dict(row), secrets), secrets


async def save_econet_config(db: AsyncSession, *, admin_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    _validate_endpoint(payload["base_url"], bool(payload.get("allow_private_network")))
    request_template = payload.get("request_template") or DEFAULT_REQUEST_TEMPLATE
    response_mapping = payload.get("response_mapping") or DEFAULT_RESPONSE_MAPPING
    json.dumps(request_template)
    json.dumps(response_mapping)

    current, current_secrets = await get_saved_econet_config(db)
    secrets_map = dict(current_secrets)
    for field in SECRET_FIELDS:
        if field in payload and payload[field] not in (None, ""):
            secrets_map[field] = payload[field]

    if payload["auth_scheme"] != "custom":
        secrets_map.pop("extra_headers", None)
    if payload["auth_scheme"] == "none":
        secrets_map.pop("api_key", None)
        secrets_map.pop("api_secret", None)
    if payload["auth_scheme"] in {"bearer", "api-key"}:
        secrets_map.pop("api_secret", None)

    cipher = SecretCipher(settings.secrets_encryption_key)
    secret_ciphertext = (
        cipher.encrypt(json.dumps(secrets_map, separators=(",", ":"))) if secrets_map else None
    )

    values = {
        "base_url": payload["base_url"].rstrip("/"),
        "chat_endpoint_path": _normalise_path(payload.get("chat_endpoint_path"), "/chat/completions"),
        "health_endpoint_path": _normalise_path(payload["health_endpoint_path"], "/health")
        if payload.get("health_endpoint_path") else None,
        "auth_scheme": payload["auth_scheme"],
        "auth_header_name": payload.get("auth_header_name") or "Authorization",
        "model": payload.get("model") or "default",
        "timeout_seconds": int(payload.get("timeout_seconds") or 60),
        "request_template": json.dumps(request_template),
        "response_mapping": json.dumps(response_mapping),
        "allow_private_network": bool(payload.get("allow_private_network")),
        "secret_ciphertext": secret_ciphertext,
        "admin_id": admin_id,
    }

    if current:
        await db.execute(
            text(
                """
                update integration_configs set
                  base_url=:base_url,
                  chat_endpoint_path=:chat_endpoint_path,
                  health_endpoint_path=:health_endpoint_path,
                  auth_scheme=:auth_scheme,
                  auth_header_name=:auth_header_name,
                  model=:model,
                  timeout_seconds=:timeout_seconds,
                  request_template=cast(:request_template as jsonb),
                  response_mapping=cast(:response_mapping as jsonb),
                  allow_private_network=:allow_private_network,
                  secret_ciphertext=:secret_ciphertext,
                  last_test_status=null,
                  last_test_kind=null,
                  last_test_at=null,
                  last_test_error=null,
                  version=version+1,
                  updated_by=:admin_id,
                  updated_at=now()
                where id=:id
                """
            ),
            {"id": current.id, **values},
        )
        target_id = current.id
    else:
        target_id = (
            await db.execute(
                text(
                    """
                    insert into integration_configs
                      (provider, environment, enabled, base_url, chat_endpoint_path,
                       health_endpoint_path, auth_scheme, auth_header_name, model,
                       timeout_seconds, request_template, response_mapping,
                       allow_private_network, secret_ciphertext, created_by, updated_by)
                    values
                      ('econet-ai', 'production', false, :base_url, :chat_endpoint_path,
                       :health_endpoint_path, :auth_scheme, :auth_header_name, :model,
                       :timeout_seconds, cast(:request_template as jsonb),
                       cast(:response_mapping as jsonb), :allow_private_network,
                       :secret_ciphertext, :admin_id, :admin_id)
                    returning id
                    """
                ),
                values,
            )
        ).scalar_one()

    return {"id": str(target_id), "status": "saved"}


async def _request(config: EconetIntegration, *, path: str, method: str,
                   body: dict[str, Any] | None, trace_id: str | None) -> httpx.Response:
    _validate_endpoint(config.base_url, config.allow_private_network)
    headers = {"Accept": "application/json", "X-NahaOS-Trace-Id": trace_id or "", **_auth_headers(config)}
    async with httpx.AsyncClient(timeout=config.timeout_seconds, follow_redirects=False) as client:
        for attempt in range(3):
            try:
                response = await client.request(
                    method=method,
                    url=f"{config.base_url}{path}",
                    json=body if method.upper() != "GET" else None,
                    headers=headers,
                )
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
                if attempt == 2:
                    raise RuntimeError("Unable to connect to Econet AI")
                await asyncio.sleep(0.25 * (2**attempt))
                continue
            if response.status_code in {429, 502, 503, 504} and attempt < 2:
                await asyncio.sleep(0.25 * (2**attempt))
                continue
            if response.status_code >= 400:
                raise _safe_http_error(response)
            return response
    raise RuntimeError("Econet AI request failed")


async def test_econet_config(config: EconetIntegration, *, smoke_chat: bool = False) -> dict[str, Any]:
    _validate_endpoint(config.base_url, config.allow_private_network)
    if config.health_endpoint_path and not smoke_chat:
        response = await _request(
            config, path=config.health_endpoint_path, method="GET",
            body=None, trace_id="nahaos-health-check"
        )
        return {"ok": True, "kind": "health", "status_code": response.status_code}

    variables = {
        "model": config.model,
        "messages": [{"role": "user", "content": "NahaOS connectivity test. Reply OK."}],
        "trace_id": "nahaos-smoke-test",
        "user_id": None,
        "session_id": None,
        "metadata": {"purpose": "connectivity_test"},
    }
    body = _render_template(config.request_template, variables)
    response = await _request(
        config, path=config.chat_endpoint_path, method="POST",
        body=body, trace_id="nahaos-smoke-test"
    )
    data = response.json()
    content = _json_path(data, config.response_mapping.get("content_path"))
    if not content:
        raise RuntimeError("Econet AI smoke test returned no assistant content")
    return {
        "ok": True,
        "kind": "chat",
        "status_code": response.status_code,
        "content_preview": str(content)[:120],
    }
