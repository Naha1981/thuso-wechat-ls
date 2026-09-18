from __future__ import annotations

from app.ai.contracts import AIProvider
from app.ai.providers import DemoAIProvider, EconetAIProvider, HTTPAIProvider
from app.core.config import get_settings


def get_ai_provider() -> AIProvider:
    settings = get_settings()
    provider = settings.ai_provider.lower()

    if provider == "demo":
        return DemoAIProvider()

    if provider == "econet":
        return EconetAIProvider(
            base_url=settings.econet_ai_base_url,
            api_key=settings.econet_ai_api_key,
            model=settings.econet_ai_model,
            endpoint_path=settings.econet_ai_endpoint_path,
            timeout=settings.econet_ai_timeout_seconds,
        )

    if provider == "http":
        return HTTPAIProvider(
            name=settings.ai_provider_name,
            base_url=settings.ai_base_url,
            api_key=settings.ai_api_key,
            model=settings.ai_model,
            timeout=settings.ai_timeout_seconds,
        )

    raise RuntimeError(f"Unsupported AI provider: {provider}")
