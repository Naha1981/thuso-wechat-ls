from __future__ import annotations

from typing import Any

from app.integrations.contracts import DemoServiceProvider, ServiceProvider, ServiceRequest, ServiceResult
from app.integrations.http_service_provider import DatabaseHTTPServiceProvider


class ServiceGateway:
    """Single policy-controlled boundary for external service-system adapters."""

    def __init__(
        self,
        providers: dict[str, ServiceProvider] | None = None,
        default_provider: ServiceProvider | None = None,
    ) -> None:
        self._providers = providers or {}
        self._default_provider = default_provider

    def register(self, domain: str, provider: ServiceProvider) -> None:
        if not domain or not domain.strip():
            raise ValueError("service domain is required")
        if domain in self._providers:
            raise ValueError(f"service provider already registered for {domain}")
        self._providers[domain] = provider

    def provider_for(self, domain: str) -> ServiceProvider:
        provider = self._providers.get(domain)
        if provider is not None:
            return provider
        if self._default_provider is not None:
            return self._default_provider
        raise LookupError(f"no service provider configured for {domain}")

    async def health(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for domain, provider in self._providers.items():
            result[domain] = await provider.health()
        if self._default_provider is not None:
            result["_default"] = await self._default_provider.health()
        return result

    async def execute(self, request: ServiceRequest) -> ServiceResult:
        provider = self.provider_for(request.domain)
        return await provider.execute(request)


def build_sandbox_gateway() -> ServiceGateway:
    gateway = ServiceGateway()
    gateway.register("demo", DemoServiceProvider())
    return gateway


def build_runtime_gateway(db) -> ServiceGateway:
    """Runtime gateway: unregistered domains resolve through the Partner Integration Hub."""
    return ServiceGateway(default_provider=DatabaseHTTPServiceProvider(db))
