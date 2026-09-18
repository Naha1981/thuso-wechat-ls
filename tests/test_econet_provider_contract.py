from uuid import uuid4

import httpx
import pytest

from app.ai.contracts import AIMessage, AIRequest
from app.ai.providers import EconetAIProvider
from app.services.econet_integration import (
    EconetIntegration,
    _auth_headers,
    _json_path,
    _normalise_path,
    _render_template,
)


def config(**overrides):
    values = dict(
        id="test",
        environment="production",
        enabled=False,
        allow_private_network=True,
        base_url="https://econet.example",
        chat_endpoint_path="/ai/chat",
        health_endpoint_path="/health",
        auth_scheme="bearer",
        auth_header_name="Authorization",
        model="caimex",
        timeout_seconds=30,
        request_template={"model": "{{model}}", "messages": "{{messages}}", "trace": "{{trace_id}}"},
        response_mapping={
            "content_path": "output.text",
            "model_path": "output.model",
            "input_units_path": "usage.in",
            "output_units_path": "usage.out",
        },
        secrets={"api_key": "secret"},
        last_test_status="passed",
        last_test_kind="chat",
        last_test_at=None,
    )
    values.update(overrides)
    return EconetIntegration(**values)


def test_auth_and_path_validation():
    assert _auth_headers(config()) == {"Authorization": "Bearer secret"}
    assert _normalise_path("/ai/chat", "/chat") == "/ai/chat"
    with pytest.raises(ValueError):
        _normalise_path("../private", "/chat")


def test_template_and_json_mapping():
    variables = {"model": "m", "trace_id": "t", "messages": [{"role": "user", "content": "hi"}]}
    rendered = _render_template(config().request_template, variables)
    assert rendered["model"] == "m"
    assert rendered["messages"][0]["content"] == "hi"
    assert _json_path({"a": {"b": [1, {"c": "ok"}]}}, "a.b.1.c") == "ok"


@pytest.mark.asyncio
async def test_econet_provider_maps_partner_response(monkeypatch):
    async def fake_request(*args, **kwargs):
        return httpx.Response(
            200,
            json={
                "output": {"text": "Hello from Econet", "model": "partner-model"},
                "usage": {"in": 11, "out": 7},
            },
            request=httpx.Request("POST", "https://econet.example/ai/chat"),
        )

    monkeypatch.setattr("app.services.econet_integration._request", fake_request)
    provider = EconetAIProvider(config=config())
    result = await provider.chat(
        AIRequest(
            messages=[AIMessage(role="user", content="Hello")],
            trace_id=str(uuid4()),
            user_id=str(uuid4()),
            session_id=None,
            metadata={"channel": "test"},
        )
    )

    assert result.provider == "econet-ai"
    assert result.model == "partner-model"
    assert result.content == "Hello from Econet"
    assert result.usage == {"input_tokens": 11, "output_tokens": 7}


@pytest.mark.asyncio
async def test_econet_provider_rejects_missing_content(monkeypatch):
    async def fake_request(*args, **kwargs):
        return httpx.Response(
            200,
            json={"output": {}, "usage": {}},
            request=httpx.Request("POST", "https://econet.example/ai/chat"),
        )

    monkeypatch.setattr("app.services.econet_integration._request", fake_request)
    provider = EconetAIProvider(config=config())
    with pytest.raises(RuntimeError, match="no assistant content"):
        await provider.chat(
            AIRequest(
                messages=[AIMessage(role="user", content="Hello")],
                trace_id=str(uuid4()),
            )
        )


@pytest.mark.asyncio
async def test_econet_provider_passes_trace_and_metadata(monkeypatch):
    captured = {}

    async def fake_request(*args, **kwargs):
        captured.update(kwargs)
        return httpx.Response(
            200,
            json={"output": {"text": "OK"}, "usage": {}},
            request=httpx.Request("POST", "https://econet.example/ai/chat"),
        )

    monkeypatch.setattr("app.services.econet_integration._request", fake_request)
    provider = EconetAIProvider(config=config())
    trace_id = str(uuid4())
    await provider.chat(
        AIRequest(
            messages=[AIMessage(role="user", content="Hello")],
            trace_id=trace_id,
            metadata={"channel": "whatsapp"},
        )
    )

    assert captured["trace_id"] == trace_id
    assert captured["path"] == "/ai/chat"

@pytest.mark.asyncio
async def test_econet_provider_uses_configured_model_when_partner_omits_model(monkeypatch):
    async def fake_request(*args, **kwargs):
        return httpx.Response(
            200,
            json={"output": {"text": "OK"}, "usage": {}},
            request=httpx.Request("POST", "https://econet.example/ai/chat"),
        )

    monkeypatch.setattr("app.services.econet_integration._request", fake_request)
    result = await EconetAIProvider(config=config()).chat(
        AIRequest(messages=[AIMessage(role="user", content="Hello")])
    )
    assert result.model == "caimex"
