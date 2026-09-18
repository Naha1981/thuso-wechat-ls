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


class EconetAIProvider:
    """NahaOS adapter boundary for Econet AI.

    This class deliberately contains no invented Econet endpoint, credential,
    scope, payload, or billing semantics. It speaks the agreed NahaOS AIProvider
    contract and isolates partner-specific HTTP mapping here.

    Until Econet supplies its signed API contract, the adapter uses a configurable
    OpenAI-compatible JSON mapping. If Econet uses a different schema, only this
    adapter needs to change; NahaOS callers do not.
    """

    name = "econet-ai"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str = "default",
        endpoint_path: str = "/chat/completions",
        timeout: float = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.endpoint_path = "/" + endpoint_path.lstrip("/")
        self.timeout = timeout

    async def chat(self, request: AIRequest) -> AIResponse:
        if not self.base_url or not self.api_key:
            raise RuntimeError("Econet AI is not configured")

        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "metadata": {
                **request.metadata,
                "trace_id": request.trace_id,
                "user_id": request.user_id,
                "session_id": request.session_id,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-NahaOS-Trace-Id": request.trace_id or "",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}{self.endpoint_path}",
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
            raise RuntimeError("Econet AI returned no assistant content")

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
            "endpoint_configured": bool(self.base_url),
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "chat": True,
            "tools": False,
            "vision": False,
            "voice": False,
            "contract_mode": "openai-compatible-placeholder",
        }


class HTTPAIProvider(EconetAIProvider):
    """Backward-compatible generic HTTP provider.

    Kept for existing integrations; new partner integrations should get a
    dedicated adapter such as EconetAIProvider.
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
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
        )
        self.name = name
