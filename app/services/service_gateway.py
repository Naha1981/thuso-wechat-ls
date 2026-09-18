from __future__ import annotations

from typing import Any

from app.integrations.contracts import DemoServiceProvider, ServiceProvider, ServiceRequest, ServiceResult


class ServiceGateway:
    """Single policy-controlled boundary for external service-system adapters."""

    def __init__(self, providers: dict[str, ServiceProvider] | None = None) -> None:
        self._providers = providers or {}

    def register(self, domain: str, provider: ServiceProvider) -> None:
        if not domain or not domain.strip():
            raise ValueError("service domain is required")
        if domain in self._providers:
            raise ValueError(f"service provider already registered for {domain}")
        self._providers[domain] = provider

    def provider_for(self, domain: str) -> ServiceProvider:
        provider = self._providers.get(domain)
        if provider is None:
            raise LookupError(f"no service provider configured for {domain}")
        return provider

    async def health(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for domain, provider in self._providers.items():
            result[domain] = await provider.health()
        return result

    async def execute(self, request: ServiceRequest) -> ServiceResult:
        provider = self.provider_for(request.domain)
        return await provider.execute(request)


def build_sandbox_gateway() -> ServiceGateway:
    gateway = ServiceGateway()
    gateway.register("demo", DemoServiceProvider())
    return gateway
