from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree as ET
from urllib.parse import parse_qs

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.partner_integrations import PartnerIntegration, json_path


def _signature(config: PartnerIntegration, body: bytes, timestamp: str) -> str:
    secret = config.secrets.get("hmac_secret")
    if not secret:
        raise RuntimeError("Webhook HMAC secret is missing")
    canonical = "\n".join((timestamp, body.decode("utf-8")))
    return hmac.new(str(secret).encode(), canonical.encode(), hashlib.sha256).hexdigest()


def verify_webhook(config: PartnerIntegration, *, headers: dict[str, str], body: bytes) -> None:
    webhook = config.webhook_config or {}
    scheme = str(webhook.get("auth_scheme", config.auth_scheme)).lower()
    if scheme == "none":
        return
    if scheme == "bearer":
        expected = config.secrets.get("api_key")
        provided = headers.get(str(webhook.get("header_name", "authorization")).lower())
        if not expected or provided != f"Bearer {expected}":
            raise PermissionError("Invalid webhook bearer credential")
        return
    if scheme == "api-key":
        expected = config.secrets.get("api_key")
        header = str(webhook.get("header_name", "x-api-key")).lower()
        if not expected or headers.get(header) != str(expected):
            raise PermissionError("Invalid webhook API key")
        return
    if scheme == "hmac_sha256":
        header = str(webhook.get("signature_header", "x-signature")).lower()
        timestamp_header = str(webhook.get("timestamp_header", "x-timestamp")).lower()
        signature = headers.get(header)
        timestamp = headers.get(timestamp_header)
        if not signature or not timestamp:
            raise PermissionError("Missing webhook signature headers")
        try:
            if abs(int(time.time()) - int(timestamp)) > int(webhook.get("max_age_seconds", 300)):
                raise PermissionError("Webhook signature timestamp is too old")
        except ValueError as exc:
            raise PermissionError("Invalid webhook signature timestamp") from exc
        expected = _signature(config, body, timestamp)
        if not hmac.compare_digest(signature.removeprefix("sha256="), expected):
            raise PermissionError("Invalid webhook signature")
        return
    raise PermissionError(f"Unsupported webhook auth scheme: {scheme}")


def parse_webhook_payload(config: PartnerIntegration, body: bytes, content_type: str) -> Any:
    adapter_type = config.adapter_type
    if adapter_type in {"rest_json", "graphql"} or "json" in content_type.lower():
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Webhook JSON body is invalid") from exc
    if adapter_type == "form_urlencoded" or "form-urlencoded" in content_type.lower():
        return {key: values[-1] if len(values) == 1 else values for key, values in parse_qs(body.decode("utf-8")).items()}
    if adapter_type == "soap_xml" or "xml" in content_type.lower():
        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            raise ValueError("Webhook XML body is invalid") from exc
        return {"xml_root": _element_to_dict(root)}
    return {"raw": body.decode("utf-8", errors="replace")}


def _element_to_dict(element: ET.Element) -> Any:
    children = list(element)
    if not children:
        return element.text or ""
    result: dict[str, Any] = {}
    for child in children:
        key = child.tag.split("}", 1)[-1]
        value = _element_to_dict(child)
        if key in result:
            if not isinstance(result[key], list):
                result[key] = [result[key]]
            result[key].append(value)
        else:
            result[key] = value
    return result


def webhook_operation(config: PartnerIntegration, payload: Any, default_operation: str) -> str:
    mapping = config.webhook_config or {}
    operation = mapping.get("operation") or default_operation
    if mapping.get("operation_path"):
        value = json_path(payload, mapping["operation_path"])
        if value:
            operation = str(value)
    return str(operation)


async def record_webhook_event(
    db: AsyncSession,
    *,
    provider_key: str,
    service_domain: str,
    operation: str,
    trace_id: str,
    event_id: str | None,
    verification_status: str,
    payload: Any,
) -> None:
    safe_payload = payload if isinstance(payload, dict) else {"data": payload}
    await db.execute(
        text("""
            insert into partner_webhook_events(
              provider_key, service_domain, operation, trace_id, event_id,
              verification_status, payload
            )
            values(
              :provider_key, :service_domain, :operation, :trace_id, :event_id,
              :verification_status, cast(:payload as jsonb)
            )
        """),
        {
            "provider_key": provider_key,
            "service_domain": service_domain,
            "operation": operation,
            "trace_id": trace_id,
            "event_id": event_id,
            "verification_status": verification_status,
            "payload": json.dumps(safe_payload, default=str),
        },
    )
