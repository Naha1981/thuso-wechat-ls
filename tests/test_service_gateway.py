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
