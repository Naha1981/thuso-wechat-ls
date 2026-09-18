import base64
from types import SimpleNamespace

import httpx
import pytest

import app.services.econet_integration as integration
from app.ai.contracts import AIMessage, AIRequest
from app.ai.providers import EconetAIProvider
from app.core.crypto import SecretCipher


def test_secret_cipher_round_trip():
    key = base64.urlsafe_b64encode(b"x" * 32).decode()
    cipher = SecretCipher(key)
    encrypted = cipher.encrypt("top-secret-value")
    assert encrypted.startswith("v1:")
    assert cipher.decrypt(encrypted) == "top-secret-value"


def test_template_and_response_mapping():
    body = integration._render_template(
        integration.DEFAULT_REQUEST_TEMPLATE,
        {
            "model": "econet-model",
            "messages": [{"role": "user", "content": "hello"}],
            "metadata": {"trace_id": "t1"},
        },
    )
    assert body["model"] == "econet-model"
    assert body["messages"][0]["content"] == "hello"
    payload = {"choices": [{"message": {"content": "OK"}}]}
    assert integration._json_path(payload, "choices.0.message.content") == "OK"


@pytest.mark.asyncio
async def test_econet_provider_uses_runtime_contract(monkeypatch):
    config = SimpleNamespace(
        id="config-1",
        environment="production",
        enabled=True,
        allow_private_network=True,
        base_url="https://econet.test",
        chat_endpoint_path="/v1/chat",
        health_endpoint_path=None,
        auth_scheme="api-key",
        auth_header_name="X-API-Key",
        model="model-1",
        timeout_seconds=10,
        request_template={
            "input": "{{messages}}",
            "model_id": "{{model}}",
            "trace": "{{trace_id}}",
        },
        response_mapping={
            "content_path": "answer",
            "model_path": "model_id",
            "input_units_path": "usage.in",
            "output_units_path": "usage.out",
        },
        secrets={"api_key": "secret"},
        last_test_status="passed",
        last_test_at=None,
    )
    monkeypatch.setattr(integration, "_validate_endpoint", lambda *args, **kwargs: None)

    with __import__("respx").MockRouter(assert_all_called=True) as router:
        route = router.post("https://econet.test/v1/chat").mock(
            return_value=httpx.Response(
                200,
                json={
                    "answer": "Connected",
                    "model_id": "model-1",
                    "usage": {"in": 2, "out": 3},
                },
            )
        )
        response = await EconetAIProvider(config=config).chat(
            AIRequest(
                messages=[AIMessage(role="user", content="hello")],
                trace_id="trace-1",
                user_id="user-1",
            )
        )

    assert route.called
    request_body = __import__("json").loads(route.calls[0].request.content)
    assert request_body["model_id"] == "model-1"
    assert request_body["input"][0]["content"] == "hello"
    assert route.calls[0].request.headers["X-API-Key"] == "secret"
    assert response.content == "Connected"
    assert response.usage == {"input_tokens": 2, "output_tokens": 3}
