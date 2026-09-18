import pytest
from uuid import uuid4

from app.services.business_outcomes import record_business_outcome


@pytest.mark.asyncio
async def test_record_business_outcome_writes_traceable_event():
    class FakeDB:
        def __init__(self):
            self.calls = []

        async def execute(self, statement, params):
            self.calls.append((str(statement), params))

    db = FakeDB()
    trace_id = uuid4()
    user_id = uuid4()

    await record_business_outcome(
        db,
        trace_id=trace_id,
        user_id=user_id,
        outcome_type="ai_subscription",
        status="observed",
        provider="econet-ai",
        service_domain="telecom",
        amount=10,
        currency="LSL",
        metadata={"classification": "observed"},
    )

    assert len(db.calls) == 1
    _, params = db.calls[0]
    assert params["trace_id"] == trace_id
    assert params["provider"] == "econet-ai"
    assert params["amount"] == 10
