from __future__ import annotations

from app.integrations.contracts import ServiceRequest, ServiceResult
from app.services.partner_integrations import execute_partner, load_active_partner


class DatabaseHTTPServiceProvider:
    """Generic production provider loaded from the NahaOS Partner Integration Hub."""

    def __init__(self, db):
        self.db = db
        self.name = "partner-http"

    async def health(self):
        return {"status": "ready", "provider": self.name}

    async def execute(self, request: ServiceRequest) -> ServiceResult:
        config = await load_active_partner(self.db, service_domain=request.domain)
        if not config:
            raise LookupError(f"no active partner integration for {request.domain}")
        data, observed = await execute_partner(
            config,
            operation=request.operation,
            trace_id=str(request.trace_id),
            payload=request.payload,
        )
        return ServiceResult(
            provider=config.provider_key,
            status="executed",
            data=data,
            observed=observed,
        )
