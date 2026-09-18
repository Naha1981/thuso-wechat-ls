from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class ServiceRequest:
    trace_id: UUID
    user_id: UUID
    domain: str
    operation: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ServiceResult:
    provider: str
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    observed: bool = False


class ServiceProvider(Protocol):
    name: str

    async def health(self) -> dict[str, Any]: ...
    async def execute(self, request: ServiceRequest) -> ServiceResult: ...


class DemoServiceProvider:
    """Deterministic sandbox provider. It cannot reach production systems."""

    name = "demo-service"

    async def health(self) -> dict[str, Any]:
        return {"status": "ok", "provider": self.name, "mode": "sandbox"}

    async def execute(self, request: ServiceRequest) -> ServiceResult:
        return ServiceResult(
            provider=self.name,
            status="simulated",
            observed=False,
            data={
                "simulation": True,
                "domain": request.domain,
                "operation": request.operation,
                "trace_id": str(request.trace_id),
            },
        )
