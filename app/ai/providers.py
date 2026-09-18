from __future__ import annotations

from typing import Any

import httpx

from app.ai.contracts import AIMessage, AIRequest, AIResponse


class DemoAIProvider:
    """Deterministic provider used when no external AI contract is available."""

    name = "demo"

    async def chat(self, request: AIRequest) -> AIResponse:
        last = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
        return AIResponse(
            provider=self.name,
            model="demo-v1",
            content=(
                "THUSO demo AI received your request. "
                "The external AI provider is not connected yet. "
                f"Request: {last[:500]}"
            ),
            usage={"input_tokens": 0, "output_tokens": 0},
        )

    async def health(self) -> dict[str, Any]:
        return {"status": "ok", "provider": self.name, "configured": True}

    def capabilities(self) -> dict[str, Any]:
        return {"chat": True, "tools": False, "vision": False, "voice": False}


class HTTPAIProvider:
    """Generic partner adapter.

    The endpoint and credential are configuration values. Partner-specific
    request/response mapping belongs in a dedicated adapter subclass once the
    signed API contract is supplied.
    """

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        api_key: str = "",
        model: str = "default",
        timeout: float = 60,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def chat(self, request: AIRequest) -> AIResponse:
        if not self.base_url or not self.api_key:
            raise RuntimeError(f"{self.name} is not configured")

        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "metadata": request.metadata,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        content = data.get("content")
        if content is None:
            choices = data.get("choices") or []
            content = (
                ((choices[0].get("message") or {}).get("content"))
                if choices
                else None
            )
        if not content:
            raise RuntimeError(f"{self.name} returned no assistant content")

        return AIResponse(
            provider=self.name,
            model=data.get("model", self.model),
            content=str(content),
            usage=data.get("usage") or {},
            raw=data,
        )

    async def health(self) -> dict[str, Any]:
        return {
            "status": "configured" if self.base_url and self.api_key else "configuration_required",
            "provider": self.name,
        }

    def capabilities(self) -> dict[str, Any]:
        return {"chat": True, "tools": False, "vision": False, "voice": False}
