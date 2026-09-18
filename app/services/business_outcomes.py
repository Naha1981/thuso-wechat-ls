from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def record_business_outcome(
    db: AsyncSession,
    *,
    trace_id: UUID,
    user_id: UUID | None,
    outcome_type: str,
    status: str,
    provider: str | None = None,
    service_domain: str | None = None,
    amount: Decimal | int | float | None = None,
    currency: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record an observable commercial/service outcome without inventing revenue."""
    await db.execute(
        text(
            """
            insert into business_outcome_events
              (trace_id, user_id, outcome_type, status, amount, currency,
               provider, service_domain, metadata)
            values
              (:trace_id, :user_id, :outcome_type, :status, :amount, :currency,
               :provider, :service_domain, cast(:metadata as jsonb))
            """
        ),
        {
            "trace_id": trace_id,
            "user_id": user_id,
            "outcome_type": outcome_type,
            "status": status,
            "amount": amount,
            "currency": currency,
            "provider": provider,
            "service_domain": service_domain,
            "metadata": json.dumps(metadata or {}, default=str),
        },
    )


async def record_action_outcome(
    db: AsyncSession,
    *,
    trace_id: UUID,
    user_id: UUID,
    action_id: UUID,
    result: dict[str, Any],
    provider: str = "nahaos",
) -> None:
    await record_business_outcome(
        db,
        trace_id=trace_id,
        user_id=user_id,
        outcome_type="service_action_completed",
        status="observed",
        provider=provider,
        service_domain=str(result.get("service_domain") or "government_or_commerce"),
        amount=result.get("amount"),
        currency=result.get("currency"),
        metadata={
            "classification": "observed",
            "action_id": str(action_id),
            "result": result,
        },
    )
