from types import SimpleNamespace
import pytest
import app.ai.gateway as gateway
from app.ai.contracts import AIMessage, AIRequest

@pytest.fixture
def demo_settings():
    return SimpleNamespace(ai_provider="demo", ai_provider_name="partner-ai", ai_base_url="", ai_api_key="", ai_model="default", ai_timeout_seconds=60)

@pytest.mark.asyncio
async def test_demo_provider_is_safe_default(monkeypatch, demo_settings):
    monkeypatch.setattr(gateway, "get_settings", lambda: demo_settings)
    provider = gateway.get_ai_provider()
    assert provider.name == "demo"
    assert (await provider.health())["status"] == "ok"

@pytest.mark.asyncio
async def test_demo_provider_returns_traceable_response(monkeypatch, demo_settings):
    monkeypatch.setattr(gateway, "get_settings", lambda: demo_settings)
    response = await gateway.get_ai_provider().chat(AIRequest(messages=[AIMessage(role="user", content="What services can I use?")], trace_id="test-trace"))
    assert response.provider == "demo"
    assert "THUSO demo AI received" in response.content

@pytest.mark.asyncio
async def test_econet_provider_maps_nahaos_contract(monkeypatch):
    settings = SimpleNamespace(
        ai_provider="econet",
        econet_ai_base_url="https://econet.example.test",
        econet_ai_api_key="secret",
        econet_ai_model="econet-model",
        econet_ai_endpoint_path="/chat/completions",
        econet_ai_timeout_seconds=10,
    )
    monkeypatch.setattr(gateway, "get_settings", lambda: settings)

    import httpx
    from respx import MockRouter

    with MockRouter(assert_all_called=True) as router:
        route = router.post("https://econet.example.test/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "econet-model",
                    "choices": [{"message": {"content": "Hello from Econet AI"}}],
                    "usage": {"input_tokens": 3, "output_tokens": 4},
                },
            )
        )
        provider = gateway.get_ai_provider()
        response = await provider.chat(
            AIRequest(
                messages=[AIMessage(role="user", content="Help me register a business")],
                user_id="user-1",
                session_id="session-1",
                trace_id="trace-1",
            )
        )

    assert route.called
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer secret"
    assert request.headers["X-NahaOS-Trace-Id"] == "trace-1"
    assert response.provider == "econet-ai"
    assert response.model == "econet-model"
    assert response.content == "Hello from Econet AI"
    assert response.usage["output_tokens"] == 4


@pytest.mark.asyncio
async def test_econet_provider_fails_closed_when_not_configured(monkeypatch):
    settings = SimpleNamespace(
        ai_provider="econet",
        econet_ai_base_url="",
        econet_ai_api_key="",
        econet_ai_model="default",
        econet_ai_endpoint_path="/chat/completions",
        econet_ai_timeout_seconds=10,
    )
    monkeypatch.setattr(gateway, "get_settings", lambda: settings)
    provider = gateway.get_ai_provider()

    with pytest.raises(RuntimeError, match="Econet AI is not configured"):
        await provider.chat(AIRequest(messages=[AIMessage(role="user", content="Hello")]))
