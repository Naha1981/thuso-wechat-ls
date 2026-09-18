import pytest

from app.ai.gateway import get_ai_provider


@pytest.mark.asyncio
async def test_demo_provider_is_safe_default(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "demo")
    provider = get_ai_provider()
    assert provider.name == "demo"
    assert (await provider.health())["status"] == "ok"


@pytest.mark.asyncio
async def test_demo_provider_returns_traceable_response():
    provider = get_ai_provider()
    response = await provider.chat(
        __import__("app.ai.contracts", fromlist=["AIRequest"]).AIRequest(
            messages=[
                __import__("app.ai.contracts", fromlist=["AIMessage"]).AIMessage(
                    role="user", content="What services can I use?"
                )
            ],
            trace_id="test-trace",
        )
    )
    assert response.provider == "demo"
    assert "THUSO demo AI received" in response.content
