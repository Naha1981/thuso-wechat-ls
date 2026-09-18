from __future__ import annotations

import asyncio
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
from app.integrations.universal_adapter import AdapterContext, adapter_for
from app.services.template_engine import json_path, render

SECRET_FIELDS = {"api_key", "api_secret", "extra_headers", "hmac_secret", "client_secret", "client_cert_pem", "client_key_pem", "ca_bundle_pem"}


@dataclass(frozen=True)
class PartnerIntegration:
    id: str
    stakeholder_name: str
    stakeholder_type: str
    service_domain: str
    provider_key: str
    environment: str
    enabled: bool
    allow_private_network: bool
    adapter_type: str
    base_url: str
    api_spec_url: str | None
    health_endpoint_path: str | None
    auth_scheme: str
    auth_header_name: str
    timeout_seconds: int
    request_defaults: dict[str, Any]
    operation_configs: dict[str, Any]
    response_mappings: dict[str, Any]
    auth_config: dict[str, Any]
    webhook_config: dict[str, Any]
    workflow_configs: dict[str, Any]
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
        allow_private_network=bool(row.get("allow_private_network", False)),
        adapter_type=row.get("adapter_type", "rest_json"),
        base_url=row["base_url"].rstrip("/"),
        api_spec_url=row.get("api_spec_url"),
        health_endpoint_path=row.get("health_endpoint_path"),
        auth_scheme=row["auth_scheme"],
        auth_header_name=row["auth_header_name"],
        timeout_seconds=max(5, min(int(row["timeout_seconds"]), 180)),
        request_defaults=row.get("request_defaults") or {},
        operation_configs=row.get("operation_configs") or {},
        response_mappings=row.get("response_mappings") or {},
        auth_config=row.get("auth_config") or {},
        webhook_config=row.get("webhook_config") or {},
        workflow_configs=row.get("workflow_configs") or {},
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
               environment, enabled, allow_private_network, adapter_type, base_url, api_spec_url, health_endpoint_path,
               auth_scheme, auth_header_name, timeout_seconds, request_defaults, operation_configs,
               response_mappings, auth_config, webhook_config, workflow_configs, secret_ciphertext,
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


async def load_active_partner_by_provider_key(db: AsyncSession, *, provider_key: str) -> PartnerIntegration | None:
    row = (
        await db.execute(
            text("""
                select id, stakeholder_name, stakeholder_type, service_domain, provider_key,
                       environment, enabled, allow_private_network, adapter_type, base_url, api_spec_url,
                       health_endpoint_path, auth_scheme, auth_header_name, timeout_seconds, request_defaults, operation_configs,
                       response_mappings, auth_config, webhook_config, workflow_configs, secret_ciphertext,
                       last_test_status, last_test_operation
                from partner_integrations
                where provider_key=:provider_key and environment='production' and enabled=true
                limit 1
            """),
            {"provider_key": provider_key},
        )
    ).mappings().first()
    if not row:
        return None
    secrets_map = {}
    if row["secret_ciphertext"]:
        secrets_map = json.loads(SecretCipher(get_settings().secrets_encryption_key).decrypt(row["secret_ciphertext"]))
    return _build(dict(row), secrets_map)


async def test_partner(config: PartnerIntegration, operation: str | None = None) -> dict[str, Any]:
    validate_endpoint(config.base_url, config.allow_private_network)
    if not operation:
        if config.health_endpoint_path:
            path = config.health_endpoint_path
            headers = {"Accept": "application/json", "X-NahaOS-Trace-Id": "nahaos-partner-health-test"}
            async with httpx.AsyncClient(timeout=config.timeout_seconds, follow_redirects=False) as client:
                response = await client.get(f"{config.base_url}{path}", headers=headers)
            if response.status_code >= 400:
                raise RuntimeError(f"Partner health endpoint returned HTTP {response.status_code}")
            return {"ok": True, "kind": "health", "status_code": response.status_code}
        operation = next(iter(config.operation_configs), None)
        if not operation:
            raise RuntimeError("Configure a health endpoint or at least one operation before testing")
    result, _ = await execute_partner(
        config,
        operation=str(operation),
        trace_id="00000000-0000-0000-0000-000000000001",
        payload={},
    )
    return {"ok": True, "kind": str(operation), "status_code": result.get("_status_code", 200), "adapter": config.adapter_type}


async def execute_partner(config: PartnerIntegration, *, operation: str, trace_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    validate_endpoint(config.base_url, config.allow_private_network)
    definition = config.operation_configs.get(operation)
    if not isinstance(definition, dict):
        raise RuntimeError(f"Partner operation not configured: {operation}")

    ctx = AdapterContext(
        base_url=config.base_url,
        operation=operation,
        trace_id=trace_id,
        timeout_seconds=config.timeout_seconds,
        request_defaults=config.request_defaults,
        operation_config=definition,
        auth_scheme=config.auth_scheme,
        auth_config=config.auth_config,
        secrets=config.secrets,
        allow_private_network=config.allow_private_network,
    )
    adapter = adapter_for(config.adapter_type)
    response = await adapter.execute(ctx, payload)

    mapping = config.response_mappings.get(operation) or definition.get("response_mapping") or {}
    if mapping:
        if not isinstance(response.data, (dict, list)):
            mapped = {"raw": response.raw_text}
        else:
            mapped = {key: json_path(response.data, path_value) for key, path_value in mapping.items()}
    else:
        mapped = response.data if isinstance(response.data, dict) else {"data": response.data}

    return {
        **mapped,
        "_adapter": config.adapter_type,
        "_status_code": response.status_code,
    }, True

async def execute_workflow(
    config: PartnerIntegration,
    *,
    workflow_name: str,
    trace_id: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    workflow = config.workflow_configs.get(workflow_name)
    if not isinstance(workflow, list) or not workflow:
        raise RuntimeError(f"Partner workflow not configured: {workflow_name}")

    results: dict[str, Any] = {}
    completed_steps: list[tuple[dict[str, Any], dict[str, Any]]] = []

    try:
        for step in workflow:
            if not isinstance(step, dict):
                raise RuntimeError("Partner workflow step must be an object")
            operation = step.get("operation")
            if not operation:
                raise RuntimeError("Partner workflow step requires an operation")

            step_payload = render(step.get("payload_template") or "{{payload}}", {
                "payload": payload,
                "steps": results,
                "trace_id": trace_id,
            })
            if not isinstance(step_payload, dict):
                raise RuntimeError(f"Workflow step {operation} payload must be an object")

            result, _ = await execute_partner(
                config,
                operation=str(operation),
                trace_id=trace_id,
                payload=step_payload,
            )
            name = str(step.get("store_as") or operation)
            results[name] = result
            completed_steps.append((step, result))
    except Exception:
        for step, previous_result in reversed(completed_steps):
            compensation = step.get("compensation_operation")
            if not compensation:
                continue
            compensation_payload = render(step.get("compensation_payload_template") or "{{previous}}", {
                "payload": payload,
                "previous": previous_result,
                "steps": results,
                "trace_id": trace_id,
            })
            if not isinstance(compensation_payload, dict):
                continue
            try:
                await execute_partner(
                    config,
                    operation=str(compensation),
                    trace_id=trace_id,
                    payload=compensation_payload,
                )
            except Exception:
                # Compensation is best-effort and the original workflow error remains authoritative.
                pass
        raise

    return {"workflow": workflow_name, "steps": results}, True

async def discover_openapi(spec_url: str) -> dict[str, Any]:
    validate_endpoint(spec_url, False)
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.get(spec_url, headers={"Accept": "application/json, application/yaml, text/yaml"})
    if response.status_code >= 400:
        raise RuntimeError(f"OpenAPI document returned HTTP {response.status_code}")
    try:
        document = response.json()
    except ValueError as exc:
        raise RuntimeError("OpenAPI document must be JSON for automatic discovery") from exc
    operations = {}
    for path, methods in (document.get("paths") or {}).items():
        if not isinstance(methods, dict):
            continue
        for method, definition in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"} or not isinstance(definition, dict):
                continue
            operation_id = definition.get("operationId") or f"{method.lower()}_{path.strip('/').replace('/', '_') or 'root'}"
            operations[str(operation_id)] = {
                "method": method.upper(),
                "path": path,
                "summary": definition.get("summary") or definition.get("description") or "",
                "request_template": {},
                "response_mapping": {},
            }
    return {
        "title": (document.get("info") or {}).get("title"),
        "version": (document.get("info") or {}).get("version"),
        "operations": operations,
    }
