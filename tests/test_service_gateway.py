from uuid import uuid4

import pytest

from app.integrations.contracts import ServiceRequest
from app.services.service_gateway import ServiceGateway, build_sandbox_gateway


@pytest.mark.asyncio
async def test_sandbox_gateway_never_claims_real_execution():
    gateway = build_sandbox_gateway()
    request = ServiceRequest(
        trace_id=uuid4(),
        user_id=uuid4(),
        domain="demo",
        operation="payment",
        payload={"amount": 10},
    )
    result = await gateway.execute(request)

    assert result.provider == "demo-service"
    assert result.status == "simulated"
    assert result.observed is False
    assert result.data["simulation"] is True


def test_gateway_requires_explicit_provider():
    gateway = ServiceGateway()
    with pytest.raises(LookupError):
        gateway.provider_for("government")

class FakeDefaultProvider:
    name = "default"

    async def health(self):
        return {"status": "ok"}

    async def execute(self, request):
        from app.integrations.contracts import ServiceResult
        return ServiceResult(provider=self.name, status="executed", data={"domain": request.domain}, observed=True)

@pytest.mark.asyncio
async def test_gateway_can_resolve_unregistered_domain_through_default_provider():
    gateway = ServiceGateway(default_provider=FakeDefaultProvider())
    result = await gateway.execute(ServiceRequest(trace_id=uuid4(), user_id=uuid4(), domain="health", operation="status"))
    assert result.provider == "default"

def test_runtime_gateway_uses_partner_hub_fallback():
    import app.services.service_gateway as gateway_module
    class DummyDB: pass
    gateway = gateway_module.build_runtime_gateway(DummyDB())
    assert gateway.provider_for("health").name == "partner-http"
