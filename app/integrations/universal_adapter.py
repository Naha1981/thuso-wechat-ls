from __future__ import annotations

import base64
import hashlib
import hmac
import json
import ssl
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import httpx

from app.services.partner_integrations import json_path, render


SUPPORTED_ADAPTERS = {
    "rest_json",
    "graphql",
    "form_urlencoded",
    "soap_xml",
}


@dataclass(frozen=True)
class AdapterContext:
    base_url: str
    operation: str
    trace_id: str
    timeout_seconds: int
    request_defaults: dict[str, Any]
    operation_config: dict[str, Any]
    auth_scheme: str
    auth_config: dict[str, Any]
    secrets: dict[str, Any]
    allow_private_network: bool


@dataclass(frozen=True)
class AdapterResponse:
    status_code: int
    headers: dict[str, str]
    data: Any
    raw_text: str


class PartnerAdapter(Protocol):
    name: str

    async def execute(self, ctx: AdapterContext, payload: dict[str, Any]) -> AdapterResponse:
        ...


def _build_ssl_context(secrets_map: dict[str, Any]) -> ssl.SSLContext | None:
    cert_pem = secrets_map.get("client_cert_pem")
    key_pem = secrets_map.get("client_key_pem")
    ca_pem = secrets_map.get("ca_bundle_pem")
    if not cert_pem or not key_pem:
        return None
    context = ssl.create_default_context()
    if ca_pem:
        context.load_verify_locations(cadata=str(ca_pem))
    cert_path = "/tmp/nahaos-client-cert.pem"
    key_path = "/tmp/nahaos-client-key.pem"
    with open(cert_path, "w", encoding="utf-8") as cert_file:
        cert_file.write(str(cert_pem))
    with open(key_path, "w", encoding="utf-8") as key_file:
        key_file.write(str(key_pem))
    context.load_cert_chain(cert_path, key_path)
    return context


class _AuthBuilder:
    token_cache: dict[str, tuple[str, float]] = {}

    @classmethod
    async def headers(cls, ctx: AdapterContext, method: str, path: str, body: bytes) -> dict[str, str]:
        scheme = ctx.auth_scheme.lower()
        config = ctx.auth_config
        secrets_map = ctx.secrets

        if scheme == "none":
            return {}

        if scheme == "bearer":
            key = secrets_map.get("api_key")
            if not key:
                raise RuntimeError("partner API credential is missing")
            return {"Authorization": f"Bearer {key}"}

        if scheme == "api-key":
            key = secrets_map.get("api_key")
            if not key:
                raise RuntimeError("partner API credential is missing")
            return {str(config.get("header_name", "X-API-Key")): str(key)}

        if scheme == "basic":
            username = secrets_map.get("api_key")
            password = secrets_map.get("api_secret")
            if not username or password is None:
                raise RuntimeError("partner basic-auth credentials are missing")
            value = base64.b64encode(f"{username}:{password}".encode()).decode()
            return {"Authorization": f"Basic {value}"}

        if scheme == "custom":
            headers = secrets_map.get("extra_headers") or {}
            return {str(k): str(v) for k, v in headers.items()}

        if scheme == "hmac_sha256":
            secret = secrets_map.get("hmac_secret")
            if not secret:
                raise RuntimeError("HMAC signing secret is missing")
            timestamp = str(int(time.time()))
            canonical = "\n".join((method.upper(), path, timestamp, body.decode("utf-8")))
            signature = hmac.new(str(secret).encode(), canonical.encode(), hashlib.sha256).hexdigest()
            timestamp_header = str(config.get("timestamp_header", "X-Timestamp"))
            signature_header = str(config.get("signature_header", "X-Signature"))
            return {
                timestamp_header: timestamp,
                signature_header: signature,
            }

        if scheme == "oauth2_client_credentials":
            token_url = config.get("token_url")
            client_id = config.get("client_id")
            client_secret = secrets_map.get("client_secret")
            if not token_url or not client_id or not client_secret:
                raise RuntimeError("OAuth2 client-credentials configuration is incomplete")
            cache_key = f"{token_url}:{client_id}"
            cached = cls.token_cache.get(cache_key)
            now = time.time()
            if cached and cached[1] > now + 30:
                return {"Authorization": f"Bearer {cached[0]}"}
            async with httpx.AsyncClient(timeout=ctx.timeout_seconds, follow_redirects=False) as client:
                response = await client.post(
                    token_url,
                    data={
                        "grant_type": "client_credentials",
                        **({"scope": config["scope"]} if config.get("scope") else {}),
                    },
                    auth=(str(client_id), str(client_secret)),
                    headers={"Accept": "application/json"},
                )
            if response.status_code >= 400:
                raise RuntimeError(f"OAuth2 token endpoint returned HTTP {response.status_code}")
            token_data = response.json()
            token = token_data.get("access_token")
            if not token:
                raise RuntimeError("OAuth2 token endpoint returned no access_token")
            expires = float(token_data.get("expires_in", 300))
            cls.token_cache[cache_key] = (str(token), now + expires)
            return {"Authorization": f"Bearer {token}"}

        if scheme == "mtls":
            if not secrets_map.get("client_cert_pem") or not secrets_map.get("client_key_pem"):
                raise RuntimeError("mTLS client certificate and key are required")
            return {}

        raise RuntimeError(f"unsupported partner auth scheme: {ctx.auth_scheme}")


def _path_from_config(config: dict[str, Any]) -> str:
    path = str(config.get("path") or "")
    if not path.startswith("/") or ".." in path:
        raise ValueError("adapter operation path must be absolute and cannot contain '..'")
    return path


async def _request(ctx: AdapterContext, *, method: str, path: str, body: bytes | None, headers: dict[str, str], content_type: str) -> AdapterResponse:
    all_headers = {
        "Accept": "application/json, application/xml, text/xml, */*",
        "X-NahaOS-Trace-Id": ctx.trace_id,
        "X-NahaOS-Idempotency-Key": ctx.trace_id,
        "Content-Type": content_type,
        **headers,
    }
    verify: ssl.SSLContext | bool = True
    if ctx.auth_scheme.lower() == "mtls":
        verify = _build_ssl_context(ctx.secrets) or True

    async with httpx.AsyncClient(timeout=ctx.timeout_seconds, follow_redirects=False, verify=verify) as client:
        for attempt in range(3):
            try:
                response = await client.request(
                    method,
                    f"{ctx.base_url}{path}",
                    content=body,
                    headers=all_headers,
                )
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
                if attempt == 2:
                    raise RuntimeError("Unable to connect to partner API")
                await __import__("asyncio").sleep(0.25 * (2**attempt))
                continue
            if response.status_code in {429, 502, 503, 504} and attempt < 2:
                await __import__("asyncio").sleep(0.25 * (2**attempt))
                continue
            break
    if response.status_code >= 400:
        raise RuntimeError(f"Partner API returned HTTP {response.status_code}")
    return AdapterResponse(
        status_code=response.status_code,
        headers=dict(response.headers),
        data=None,
        raw_text=response.text,
    )


def _render_payload(node: Any, payload: dict[str, Any], ctx: AdapterContext) -> Any:
    return render(node, {
        "trace_id": ctx.trace_id,
        "operation": ctx.operation,
        "payload": payload,
    })


class RestJsonAdapter:
    name = "rest_json"

    async def execute(self, ctx: AdapterContext, payload: dict[str, Any]) -> AdapterResponse:
        path = _path_from_config(ctx.operation_config)
        method = str(ctx.operation_config.get("method", "POST")).upper()
        body_obj = _render_payload(
            {**ctx.request_defaults, **(ctx.operation_config.get("request_template") or {})},
            payload,
            ctx,
        )
        body = json.dumps(body_obj).encode() if method != "GET" else None
        headers = await _AuthBuilder.headers(ctx, method, path, body or b"")
        response = await _request(ctx, method=method, path=path, body=body, headers=headers, content_type="application/json")
        try:
            response_data = response.raw_text and json.loads(response.raw_text)
        except json.JSONDecodeError:
            response_data = {"raw": response.raw_text}
        return AdapterResponse(response.status_code, response.headers, response_data, response.raw_text)


class FormUrlEncodedAdapter:
    name = "form_urlencoded"

    async def execute(self, ctx: AdapterContext, payload: dict[str, Any]) -> AdapterResponse:
        path = _path_from_config(ctx.operation_config)
        method = str(ctx.operation_config.get("method", "POST")).upper()
        values = _render_payload(
            {**ctx.request_defaults, **(ctx.operation_config.get("request_template") or {"payload": "{{payload}}"})},
            payload,
            ctx,
        )
        if isinstance(values, dict) and set(values) == {"payload"}:
            values = values["payload"]
        if not isinstance(values, dict):
            raise RuntimeError("form_urlencoded request template must render to an object")
        body = urlencode({str(k): str(v) for k, v in values.items()}).encode()
        headers = await _AuthBuilder.headers(ctx, method, path, body)
        response = await _request(ctx, method=method, path=path, body=body, headers=headers, content_type="application/x-www-form-urlencoded")
        try:
            data = json.loads(response.raw_text)
        except json.JSONDecodeError:
            data = {"raw": response.raw_text}
        return AdapterResponse(response.status_code, response.headers, data, response.raw_text)


class GraphQLAdapter:
    name = "graphql"

    async def execute(self, ctx: AdapterContext, payload: dict[str, Any]) -> AdapterResponse:
        path = _path_from_config(ctx.operation_config)
        method = str(ctx.operation_config.get("method", "POST")).upper()
        query = ctx.operation_config.get("query")
        if not query:
            raise RuntimeError("GraphQL operation requires query")
        body_obj = {
            "query": str(query),
            "variables": _render_payload(ctx.operation_config.get("variables") or "{{payload}}", payload, ctx),
            "operationName": ctx.operation_config.get("operation_name"),
        }
        body = json.dumps(body_obj).encode()
        headers = await _AuthBuilder.headers(ctx, method, path, body)
        response = await _request(ctx, method=method, path=path, body=body, headers=headers, content_type="application/json")
        try:
            data = json.loads(response.raw_text)
        except json.JSONDecodeError:
            raise RuntimeError("GraphQL endpoint returned non-JSON response")
        if data.get("errors"):
            raise RuntimeError("GraphQL operation returned errors")
        return AdapterResponse(response.status_code, response.headers, data, response.raw_text)


class SoapXmlAdapter:
    name = "soap_xml"

    async def execute(self, ctx: AdapterContext, payload: dict[str, Any]) -> AdapterResponse:
        path = _path_from_config(ctx.operation_config)
        method = str(ctx.operation_config.get("method", "POST")).upper()
        xml_template = ctx.operation_config.get("xml_template")
        if not xml_template:
            raise RuntimeError("SOAP operation requires xml_template")
        xml_text = render(xml_template, {
            "trace_id": ctx.trace_id,
            "operation": ctx.operation,
            "payload": payload,
        })
        if not isinstance(xml_text, str):
            raise RuntimeError("SOAP xml_template must render to text")
        ET.fromstring(xml_text)
        body = xml_text.encode()
        headers = await _AuthBuilder.headers(ctx, method, path, body)
        headers["SOAPAction"] = str(ctx.operation_config.get("soap_action", ""))
        response = await _request(ctx, method=method, path=path, body=body, headers=headers, content_type="text/xml")
        try:
            root = ET.fromstring(response.raw_text)
            data = {"xml_root": _element_to_dict(root)}
        except ET.ParseError:
            data = {"raw": response.raw_text}
        return AdapterResponse(response.status_code, response.headers, data, response.raw_text)


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


def adapter_for(adapter_type: str) -> PartnerAdapter:
    adapters: dict[str, PartnerAdapter] = {
        "rest_json": RestJsonAdapter(),
        "form_urlencoded": FormUrlEncodedAdapter(),
        "graphql": GraphQLAdapter(),
        "soap_xml": SoapXmlAdapter(),
    }
    try:
        return adapters[adapter_type]
    except KeyError as exc:
        raise RuntimeError(f"Unsupported partner adapter: {adapter_type}") from exc
