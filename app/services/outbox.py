import json
import uuid
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def enqueue(db: AsyncSession, aggregate_type: str, aggregate_id: UUID, event_type: str, payload: dict):
    await db.execute(text("""
      insert into outbox_events(aggregate_type,aggregate_id,event_type,payload)
      values (:aggregate_type,:aggregate_id,:event_type,cast(:payload as jsonb))
    """), {"aggregate_type":aggregate_type,"aggregate_id":aggregate_id,"event_type":event_type,"payload":json.dumps(payload)})

async def enqueue_channel(db: AsyncSession, channel: str, recipient: str, message_type: str, payload: dict, account_key: str | None = None, trace_id: str | None = None):
    if channel == 'whatsapp':
        from app.services.whatsapp_account_routing import resolve_outbound_account
        resolved = await resolve_outbound_account(db, recipient=recipient, explicit_account_key=account_key or payload.get('account_key'))
        account_key = resolved.account_key
        payload = {**payload, 'account_key': account_key}
    else:
        account_key = account_key or payload.get('account_key')
    idem = payload.get('idempotency_key') or f"{channel}:{recipient}:{message_type}:{payload.get('body','')}"
    await db.execute(text("""
      insert into outbox_messages(channel,recipient,message_type,payload,account_key,idempotency_key,trace_id)
      values (:channel,:recipient,:message_type,cast(:payload as jsonb),:account_key,:idempotency_key,:trace_id)
      on conflict(idempotency_key) do nothing
    """), {"channel":channel,"recipient":recipient,"message_type":message_type,
      "payload":json.dumps(payload),"account_key":account_key,"idempotency_key":idem,"trace_id":trace_id})

async def claim_messages(db: AsyncSession, limit: int = 25):
    rows = (await db.execute(text("""
      with picked as (
        select id from outbox_messages
        where status='pending' and available_at<=now()
        order by created_at
        for update skip locked limit :limit
      )
      update outbox_messages o set status='processing', attempts=attempts+1
      from picked where o.id=picked.id
      returning o.*
    """), {"limit":limit})).mappings().all()
    return [dict(r) for r in rows]
