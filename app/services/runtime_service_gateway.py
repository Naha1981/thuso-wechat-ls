from __future__ import annotations

from app.integrations.contracts import ServiceRequest, ServiceResult
from app.services.partner_integrations import execute_partner, load_active_partner


async def execute_configured_service(db, request: ServiceRequest) -> ServiceResult:
    """Execute a production stakeholder API using only its stored contract."""
    config = await load_active_partner(db, service_domain=request.domain)
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
