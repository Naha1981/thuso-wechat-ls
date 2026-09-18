from __future__ import annotations

import hashlib
import ipaddress
import json
import secrets
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import SecretCipher

SECRET_FIELDS = {"api_key", "api_secret", "extra_headers"}


@dataclass(frozen=True)
class PartnerIntegration:
    id: str
    stakeholder_name: str
    stakeholder_type: str
    service_domain: str
    provider_key: str
    environment: str
    enabled: bool
    base_url: str
    api_spec_url: str | None
    health_endpoint_path: str | None
    auth_scheme: str
    auth_header_name: str
    timeout_seconds: int
    request_defaults: dict[str, Any]
    operation_configs: dict[str, Any]
    response_mappings: dict[str, Any]
    secrets: dict[str, Any]
    last_test_status: str | None
    last_test_operation: str | None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def validate_endpoint(base_url: str, allow_private_network: bool = False) -> None:
    parsed = httpx.URL(base_url)
    if parsed.scheme not in {"https", "http"} or not parsed.host:
        raise ValueError("base URL must be a valid HTTP(S) URL")
    if parsed.scheme == "http" and get_settings().app_env.lower() in {"prod", "production"}:
        raise ValueError("Production partner endpoints must use HTTPS")
    if allow_private_network:
        return
    try:
        addresses = socket.getaddrinfo(parsed.host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("partner hostname could not be resolved") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("partner endpoint resolves to a private/reserved network")


def normalise_path(path: str | None, default: str | None = None) -> str | None:
    if not path:
        return default
    value = path.strip()
    if not value.startswith("/") or ".." in value:
        raise ValueError("endpoint paths must be absolute and cannot contain '..'")
    return value


def render(node: Any, variables: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        return {k: render(v, variables) for k, v in node.items()}
    if isinstance(node, list):
        return [render(v, variables) for v in node]
    if isinstance(node, str) and node.startswith("{{") and node.endswith("}}") and node.count("{{") == 1:
        return variables.get(node[2:-2].strip(), node)
    if isinstance(node, str):
        value = node
        for key, item in variables.items():
            value = value.replace("{{" + key + "}}", str(item))
        return value
    return node


def json_path(value: Any, path: str | None) -> Any:
    if not path:
        return value
    current = value
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(path)
    return current


def auth_headers(config: PartnerIntegration) -> dict[str, str]:
    scheme = config.auth_scheme.lower()
    if scheme == "none":
        return {}
    if scheme in {"bearer", "api-key"}:
        key = config.secrets.get("api_key")
        if not key:
            raise RuntimeError("partner API credential is missing")
        return {"Authorization": f"Bearer {key}"} if scheme == "bearer" else {config.auth_header_name: str(key)}
    if scheme == "basic":
        import base64
        username = config.secrets.get("api_key")
        password = config.secrets.get("api_secret")
        if not username or password is None:
            raise RuntimeError("partner basic-auth credentials are missing")
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    if scheme == "custom":
        headers = config.secrets.get("extra_headers") or {}
        return {str(k): str(v) for k, v in headers.items()}
    raise RuntimeError(f"unsupported auth scheme: {config.auth_scheme}")


def _build(row: dict[str, Any], secrets_map: dict[str, Any]) -> PartnerIntegration:
    return PartnerIntegration(
        id=str(row["id"]),
        stakeholder_name=row["stakeholder_name"],
        stakeholder_type=row["stakeholder_type"],
        service_domain=row["service_domain"],
        provider_key=row["provider_key"],
        environment=row["environment"],
        enabled=bool(row["enabled"]),
        base_url=row["base_url"].rstrip("/"),
        api_spec_url=row.get("api_spec_url"),
        health_endpoint_path=row.get("health_endpoint_path"),
        auth_scheme=row["auth_scheme"],
        auth_header_name=row["auth_header_name"],
        timeout_seconds=max(5, min(int(row["timeout_seconds"]), 180)),
        request_defaults=row.get("request_defaults") or {},
        operation_configs=row.get("operation_configs") or {},
        response_mappings=row.get("response_mappings") or {},
        secrets=secrets_map,
        last_test_status=row.get("last_test_status"),
        last_test_operation=row.get("last_test_operation"),
    )


async def load_active_partner(db: AsyncSession, *, service_domain: str, provider_key: str | None = None) -> PartnerIntegration | None:
    clause = "and provider_key=:provider_key" if provider_key else ""
    params = {"service_domain": service_domain}
    if provider_key:
        params["provider_key"] = provider_key
    row = (await db.execute(text(f"""
        select id, stakeholder_name, stakeholder_type, service_domain, provider_key,
               environment, enabled, base_url, api_spec_url, health_endpoint_path,
               auth_scheme, auth_header_name, timeout_seconds, request_defaults,
               operation_configs, response_mappings, secret_ciphertext,
               last_test_status, last_test_operation
        from partner_integrations
        where service_domain=:service_domain and environment='production' and enabled=true {clause}
        order by updated_at desc limit 1
    """), params)).mappings().first()
    if not row:
        return None
    secrets_map = {}
    if row["secret_ciphertext"]:
        secrets_map = json.loads(SecretCipher(get_settings().secrets_encryption_key).decrypt(row["secret_ciphertext"]))
    return _build(dict(row), secrets_map)


async def test_partner(config: PartnerIntegration, operation: str | None = None) -> dict[str, Any]:
    validate_endpoint(config.base_url, False)
    if not operation:
        if config.health_endpoint_path:
            path = config.health_endpoint_path
            method = "GET"
            body = None
            kind = "health"
        else:
            operation = next(iter(config.operation_configs), None)
            if not operation:
                raise RuntimeError("Configure a health endpoint or at least one operation before testing")
    if operation:
        definition = config.operation_configs.get(operation)
        if not isinstance(definition, dict):
            raise RuntimeError(f"Unknown partner operation: {operation}")
        path = normalise_path(definition.get("path"), None)
        if not path:
            raise RuntimeError("Operation path is required")
        method = str(definition.get("method", "POST")).upper()
        body = render({**config.request_defaults, **(definition.get("request_template") or {})}, {
            "trace_id": "nahaos-partner-smoke",
            "operation": operation,
            "payload": {},
        })
        kind = operation
    headers = {"Accept": "application/json", "X-NahaOS-Trace-Id": "nahaos-partner-smoke", **auth_headers(config)}
    async with httpx.AsyncClient(timeout=config.timeout_seconds, follow_redirects=False) as client:
        response = await client.request(method, f"{config.base_url}{path}", json=body if method != "GET" else None, headers=headers)
    if response.status_code >= 400:
        raise RuntimeError(f"Partner API returned HTTP {response.status_code}")
    return {"ok": True, "kind": kind, "status_code": response.status_code}


async def execute_partner(config: PartnerIntegration, *, operation: str, trace_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    definition = config.operation_configs.get(operation)
    if not isinstance(definition, dict):
        raise RuntimeError(f"Partner operation not configured: {operation}")
    path = normalise_path(definition.get("path"), None)
    method = str(definition.get("method", "POST")).upper()
    if not path:
        raise RuntimeError("Partner operation path is required")
    variables = {"trace_id": trace_id, "operation": operation, "payload": payload}
    body = render({**config.request_defaults, **(definition.get("request_template") or {})}, variables)
    headers = {"Accept": "application/json", "X-NahaOS-Trace-Id": trace_id, **auth_headers(config)}
    async with httpx.AsyncClient(timeout=config.timeout_seconds, follow_redirects=False) as client:
        response = await client.request(method, f"{config.base_url}{path}", json=body if method != "GET" else None, headers=headers)
    if response.status_code >= 400:
        raise RuntimeError(f"Partner API returned HTTP {response.status_code}")
    data = response.json()
    mapping = config.response_mappings.get(operation) or definition.get("response_mapping") or {}
    mapped = {key: json_path(data, path_value) for key, path_value in mapping.items()} if mapping else data
    return mapped, True
