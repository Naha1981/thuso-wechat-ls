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