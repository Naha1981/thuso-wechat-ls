from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def record_ai_usage(
    db: AsyncSession,
    *,
    trace_id: UUID,
    user_id: UUID | None,
    provider: str,
    model: str,
    channel: str,
    usage: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    await db.execute(
        text(
            """
            insert into ai_usage_events
              (trace_id, user_id, provider, model, channel, event_type,
               input_units, output_units, metadata)
            values
              (:trace_id, :user_id, :provider, :model, :channel, 'chat',
               :input_units, :output_units, cast(:metadata as jsonb))
            """
        ),
        {
            "trace_id": trace_id,
            "user_id": user_id,
            "provider": provider,
            "model": model,
            "channel": channel,
            "input_units": usage.get("input_tokens"),
            "output_units": usage.get("output_tokens"),
            "metadata": json.dumps(metadata or {}),
        },
    )
