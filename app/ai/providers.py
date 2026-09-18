from __future__ import annotations

from typing import Any

import httpx

from app.ai.contracts import AIRequest, AIResponse
from app.core.config import get_settings


class DemoAIProvider:
    """Deterministic sandbox provider. It never calls Econet."""

    name = "demo"

    async def chat(self, request: AIRequest) -> AIResponse:
        last = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
        return AIResponse(
            provider=self.name,
            model="demo-v1",
            content=(
                "NahaOS Sandbox AI received your request. "
                "This environment is isolated from production provider credentials. "
                f"Request: {last[:500]}"
            ),
            usage={"input_tokens": 0, "output_tokens": 0},
        )

    async def health(self) -> dict[str, Any]:
        return {"status": "ok", "provider": self.name, "mode": "sandbox"}

    def capabilities(self) -> dict[str, Any]:
        return {"chat": True, "tools": False, "vision": False, "voice": False, "mode": "sandbox"}


class EconetAIProvider:
    """Production Econet adapter behind the stable NahaOS AIProvider contract."""

    name = "econet-ai"

    def __init__(self, *, config=None, base_url: str = "", api_key: str = "", model: str = "default",
                 endpoint_path: str = "/chat/completions", timeout: float = 60) -> None:
        self.config = config
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.endpoint_path = "/" + endpoint_path.lstrip("/")
        self.timeout = timeout

    def _config(self):
        if self.config is not None:
            return self.config

        from app.services.econet_integration import build_econet_config
        return build_econet_config(
            {
                "id": "environment",
                "environment": "production",
                "enabled": True,
                "base_url": self.base_url,
                "chat_endpoint_path": self.endpoint_path,
                "health_endpoint_path": None,
                "auth_scheme": "bearer",
                "auth_header_name": "Authorization",
                "model": self.model,
                "timeout_seconds": int(self.timeout),
                "request_template": {},
                "response_mapping": {},
                "last_test_status": "passed",
                "last_test_at": None,
            },
            {"api_key": self.api_key},
        )

    async def chat(self, request: AIRequest) -> AIResponse:
        from app.services.econet_integration import (
            DEFAULT_REQUEST_TEMPLATE,
            DEFAULT_RESPONSE_MAPPING,
            _json_path,
            _render_template,
            _request,
        )

        config = self._config()
        if not config.base_url:
            raise RuntimeError("Econet AI is not configured")

        variables = {
            "model": config.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "trace_id": request.trace_id,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "metadata": request.metadata,
        }
        template = config.request_template or DEFAULT_REQUEST_TEMPLATE
        body = _render_template(template, variables)
        response = await _request(
            config,
            path=config.chat_endpoint_path,
            method="POST",
            body=body,
            trace_id=request.trace_id,
        )
        data = response.json()
        mapping = config.response_mapping or DEFAULT_RESPONSE_MAPPING

        content = _json_path(data, mapping.get("content_path"))
        if not content:
            raise RuntimeError("Econet AI returned no assistant content")

        model = _json_path(data, mapping.get("model_path")) or config.model
        usage = {}
        input_path = mapping.get("input_units_path")
        output_path = mapping.get("output_units_path")
        if input_path:
            try:
                usage["input_tokens"] = _json_path(data, input_path)
            except (KeyError, IndexError, TypeError, ValueError):
                pass
        if output_path:
            try:
                usage["output_tokens"] = _json_path(data, output_path)
            except (KeyError, IndexError, TypeError, ValueError):
                pass

        return AIResponse(
            provider=self.name,
            model=str(model),
            content=str(content),
            usage=usage,
            raw=data,
        )

    async def health(self) -> dict[str, Any]:
        config = self._config()
        if not config.base_url:
            return {"status": "configuration_required", "provider": self.name}
        if config.last_test_status == "passed":
            return {"status": "ready", "provider": self.name, "environment": config.environment}
        return {"status": "configured", "provider": self.name, "environment": config.environment}

    def capabilities(self) -> dict[str, Any]:
        return {
            "chat": True,
            "tools": False,
            "vision": False,
            "voice": False,
            "configuration": "portal",
            "environment": "production",
        }


class HTTPAIProvider(EconetAIProvider):
    """Backward-compatible generic partner adapter."""

    def __init__(self, *, name: str, base_url: str, api_key: str = "", model: str = "default", timeout: float = 60):
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            model=model,
            endpoint_path="/chat/completions",
            timeout=timeout,
        )
        self.name = name
