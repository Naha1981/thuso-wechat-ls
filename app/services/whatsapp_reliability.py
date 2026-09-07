from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_ATTEMPTS = 8

async def record_inbox_event(db: AsyncSession, *, transport: str, account_key: str | None,
                             external_event_id: str, event_type: str, payload: dict) -> tuple[uuid.UUID, bool]:
    row = (await db.execute(text("""
      insert into whatsapp_inbox_events(transport,account_key,external_event_id,event_type,payload,trace_id)
      values(:transport,:account_key,:external_id,:event_type,cast(:payload as jsonb),coalesce(:trace_id,gen_random_uuid()))
      on conflict(transport,account_key,external_event_id) do nothing
      returning id
    """), {"transport": transport, "account_key": account_key, "external_id": external_event_id,
          "event_type": event_type, "payload": json.dumps(payload), "trace_id": payload.get("trace_id")})).first()
    if row:
        return row[0], True
    existing = (await db.execute(text("""
      select id from whatsapp_inbox_events
      where transport=:transport and account_key is not distinct from :account_key
        and external_event_id=:external_id
    """), {"transport": transport, "account_key": account_key, "external_id": external_event_id})).scalar_one()
    return existing, False

async def mark_inbox_processing(db: AsyncSession, event_id: uuid.UUID) -> None:
    await db.execute(text("""update whatsapp_inbox_events
      set status='processing',attempts=attempts+1,locked_at=now()
      where id=:id and status in ('received','failed')"""), {"id": event_id})

async def mark_inbox_processed(db: AsyncSession, event_id: uuid.UUID) -> None:
    await db.execute(text("""update whatsapp_inbox_events
      set status='processed',processed_at=now(),locked_at=null,last_error=null
      where id=:id"""), {"id": event_id})

async def mark_inbox_failed(db: AsyncSession, event_id: uuid.UUID, error: str) -> None:
    await db.execute(text("""update whatsapp_inbox_events
      set status=case when attempts >= :max_attempts then 'dead_letter' else 'failed' end,
          available_at=now()+make_interval(secs=>least(900,greatest(5,power(2,attempts)::int*5))),
          locked_at=null,last_error=:error where id=:id"""),
                     {"id": event_id, "error": error[:2000], "max_attempts": MAX_ATTEMPTS})

async def claim_inbox_events(db: AsyncSession, limit: int = 25) -> list[dict]:
    rows = (await db.execute(text("""
      with picked as (
        select id from whatsapp_inbox_events
        where status in ('received','failed') and available_at<=now()
        order by created_at for update skip locked limit :limit
      )
      update whatsapp_inbox_events e set status='processing',attempts=attempts+1,locked_at=now()
      from picked where e.id=picked.id returning e.*
    """), {"limit": limit})).mappings().all()
    return [dict(r) for r in rows]

async def record_outbound_receipt(db: AsyncSession, *, outbox_message_id: uuid.UUID,
                                  transport: str, provider_message_id: str | None,
                                  status: str, metadata: dict | None = None,
                                  occurred_at: datetime | None = None) -> None:
    await db.execute(text("""
      insert into whatsapp_delivery_receipts(outbox_message_id,transport,provider_message_id,status,occurred_at,metadata)
      values(:oid,:transport,:pid,:status,:occurred_at,cast(:metadata as jsonb))
      on conflict(transport,provider_message_id,status) do nothing
    """), {"oid": outbox_message_id, "transport": transport, "pid": provider_message_id,
          "status": status, "occurred_at": occurred_at or datetime.now(timezone.utc),
          "metadata": json.dumps(metadata or {})})
    await db.execute(text("""update outbox_messages set receipt_status=:status,receipt_at=now(),
      provider_message_id=coalesce(provider_message_id,:pid) where id=:oid"""),
                     {"status": status, "pid": provider_message_id, "oid": outbox_message_id})

async def recover_stale_inbox_events(db: AsyncSession, stale_seconds: int = 300) -> int:
    """Return abandoned processing events to the retry queue after a worker crash."""
    result = await db.execute(text("""
      update whatsapp_inbox_events
      set status='failed', available_at=now(), locked_at=null,
          last_error=coalesce(last_error,'worker lease expired')
      where status='processing'
        and locked_at < now() - make_interval(secs=>:seconds)
      returning id
    """), {'seconds': stale_seconds})
    return len(result.fetchall())


async def health_success(db: AsyncSession, wa_account_id: uuid.UUID, transport: str) -> None:
    await db.execute(text("""
      insert into whatsapp_account_health(wa_account_id,transport,state,consecutive_failures,last_success_at,updated_at)
      values(:id,:transport,'healthy',0,now(),now())
      on conflict(wa_account_id) do update set transport=:transport,state='healthy',consecutive_failures=0,
      last_success_at=now(),last_error=null,circuit_open_until=null,updated_at=now()
    """), {"id": wa_account_id, "transport": transport})

async def health_failure(db: AsyncSession, wa_account_id: uuid.UUID, transport: str, error: str) -> None:
    await db.execute(text("""
      insert into whatsapp_account_health(wa_account_id,transport,state,consecutive_failures,last_failure_at,last_error,updated_at)
      values(:id,:transport,'degraded',1,now(),:error,now())
      on conflict(wa_account_id) do update set transport=:transport,
      consecutive_failures=whatsapp_account_health.consecutive_failures+1,
      state=case when whatsapp_account_health.consecutive_failures+1 >= 5 then 'circuit_open' else 'degraded' end,
      last_failure_at=now(),last_error=:error,updated_at=now()
    """), {"id": wa_account_id, "transport": transport, "error": error[:2000]})
