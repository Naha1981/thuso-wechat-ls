from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

STREAM = "naha:marketplace:events"
GROUP = "marketplace-workers"

@dataclass(frozen=True)
class MarketplaceEvent:
    event_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    payload: dict

async def ensure_consumer_group(redis: Redis) -> None:
    try:
        await redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise

async def publish_event(redis: Redis, event: MarketplaceEvent) -> str:
    return await redis.xadd(STREAM, {
        "event_id": str(event.event_id),
        "event_type": event.event_type,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": str(event.aggregate_id),
        "payload": json.dumps(event.payload, separators=(",", ":")),
    }, maxlen=100_000, approximate=True)

async def claim_outbox_events(db: AsyncSession, limit: int = 50) -> list[dict]:
    rows = (await db.execute(text("""
      with picked as (
        select id from outbox_events
        where status='pending' and available_at<=now()
        order by created_at
        for update skip locked limit :limit
      )
      update outbox_events o
         set status='processing', attempts=attempts+1, locked_at=now()
        from picked
       where o.id=picked.id
      returning o.*
    """), {"limit": limit})).mappings().all()
    return [dict(r) for r in rows]

async def mark_event_published(db: AsyncSession, event_id: UUID, stream_id: str) -> None:
    await db.execute(text("""
      update outbox_events set status='published', processed_at=now(), locked_at=null, last_error=null
      where id=:id
    """), {"id": event_id})
    await db.execute(text("""
      insert into marketplace_event_log(event_id,event_type,aggregate_type,aggregate_id,stream_id)
      select id,event_type,aggregate_type,aggregate_id,:stream_id from outbox_events where id=:id
      on conflict(event_id) do update set stream_id=excluded.stream_id, delivered_at=now()
    """), {"id": event_id, "stream_id": stream_id})

async def mark_event_failed(db: AsyncSession, event_id: UUID, error: str) -> None:
    await db.execute(text("""
      update outbox_events
         set status=case when attempts>=10 then 'failed' else 'pending' end,
             locked_at=null,
             available_at=now()+make_interval(secs=>least(600,(2^least(attempts,8))*2)::int),
             last_error=:error
       where id=:id
    """), {"id": event_id, "error": error[:2000]})

async def acquire_dispatch_lease(db: AsyncSession, request_id: UUID, owner: str, ttl_seconds: int = 30) -> bool:
    row = (await db.execute(text("""
      insert into dispatch_locks(service_request_id,lease_until,owner)
      values(:rid,now()+make_interval(secs=>:ttl),:owner)
      on conflict(service_request_id) do update
        set lease_until=excluded.lease_until, owner=excluded.owner, updated_at=now()
      where dispatch_locks.lease_until<=now() or dispatch_locks.owner=:owner
      returning service_request_id
    """), {"rid": request_id, "ttl": ttl_seconds, "owner": owner})).first()
    return row is not None

async def release_dispatch_lease(db: AsyncSession, request_id: UUID, owner: str) -> None:
    await db.execute(text("delete from dispatch_locks where service_request_id=:rid and owner=:owner"),
                     {"rid": request_id, "owner": owner})
