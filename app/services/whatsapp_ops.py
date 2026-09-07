from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def normalize_health(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "wa_account_id": str(row["wa_account_id"]),
        "transport": row["transport"],
        "state": row["state"],
        "consecutive_failures": int(row.get("consecutive_failures") or 0),
        "last_success_at": _iso(row.get("last_success_at")),
        "last_failure_at": _iso(row.get("last_failure_at")),
        "last_error": row.get("last_error"),
        "circuit_open_until": _iso(row.get("circuit_open_until")),
        "updated_at": _iso(row.get("updated_at")),
    }


async def overview(db: AsyncSession) -> dict[str, Any]:
    inbox = (await db.execute(text("""
        select
          count(*) filter (where status='received') as received,
          count(*) filter (where status='processing') as processing,
          count(*) filter (where status='failed') as failed,
          count(*) filter (where status='dead_letter') as dead_letter,
          count(*) filter (where status='processed') as processed,
          coalesce(avg(extract(epoch from (processed_at-created_at))) filter (where processed_at is not null),0) as avg_processing_seconds
        from whatsapp_inbox_events
    """))).mappings().one()
    outbox = (await db.execute(text("""
        select
          count(*) filter (where status='pending') as pending,
          count(*) filter (where status='sent') as sent,
          count(*) filter (where receipt_status='delivered') as delivered,
          count(*) filter (where receipt_status='read') as read,
          count(*) filter (where status='failed') as failed
        from outbox_messages
        where channel='whatsapp'
    """))).mappings().one()
    accounts = (await db.execute(text("""
        select
          count(*) filter (where coalesce(revoked_at, null) is null) as active,
          count(*) filter (where coalesce(revoked_at, null) is not null) as revoked
        from wa_accounts
    """))).mappings().one()
    health = (await db.execute(text("""
        select
          count(*) filter (where state='healthy') as healthy,
          count(*) filter (where state='degraded') as degraded,
          count(*) filter (where state='circuit_open') as circuit_open,
          count(*) as tracked
        from whatsapp_account_health
    """))).mappings().one()
    return {
        "inbox": {
            "received": int(inbox["received"] or 0),
            "processing": int(inbox["processing"] or 0),
            "failed": int(inbox["failed"] or 0),
            "dead_letter": int(inbox["dead_letter"] or 0),
            "processed": int(inbox["processed"] or 0),
            "avg_processing_seconds": float(inbox["avg_processing_seconds"] or 0),
        },
        "outbox": {k: int(outbox[k] or 0) for k in ("pending", "sent", "delivered", "read", "failed")},
        "accounts": {"active": int(accounts["active"] or 0), "revoked": int(accounts["revoked"] or 0)},
        "health": {k: int(health[k] or 0) for k in ("healthy", "degraded", "circuit_open", "tracked")},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def account_health(db: AsyncSession, limit: int = 100) -> list[dict[str, Any]]:
    rows = (await db.execute(text("""
        select h.*, a.account_key, a.label, a.transport as account_transport, a.status as account_status
        from whatsapp_account_health h
        join wa_accounts a on a.id=h.wa_account_id
        order by h.updated_at desc
        limit :limit
    """), {"limit": min(max(limit, 1), 1000)})).mappings().all()
    result=[]
    for r in rows:
        item=normalize_health(dict(r))
        item.update({"account_key": r["account_key"], "label": r["label"], "account_transport": r["account_transport"], "account_status": r["account_status"]})
        result.append(item)
    return result


async def recent_failures(db: AsyncSession, limit: int = 50) -> dict[str, list[dict[str, Any]]]:
    limit=min(max(limit,1),500)
    inbox=(await db.execute(text("""
      select id,transport,account_key,external_event_id,event_type,status,attempts,last_error,created_at,updated_at
      from whatsapp_inbox_events
      where status in ('failed','dead_letter')
      order by created_at desc limit :limit
    """),{"limit":limit})).mappings().all()
    outbox=(await db.execute(text("""
      select id,account_key,recipient,status,attempts,last_error,available_at,created_at
      from outbox_messages
      where channel='whatsapp' and status='failed'
      order by created_at desc limit :limit
    """),{"limit":limit})).mappings().all()
    def clean(row):
        d=dict(row)
        for k,v in list(d.items()):
            if isinstance(v,datetime): d[k]=_iso(v)
        if "id" in d: d["id"]=str(d["id"])
        return d
    return {"inbox":[clean(r) for r in inbox],"outbox":[clean(r) for r in outbox]}


async def reset_circuit(db: AsyncSession, wa_account_id: str) -> bool:
    result=await db.execute(text("""
      update whatsapp_account_health
      set state='degraded', consecutive_failures=0, circuit_open_until=null, last_error=null, updated_at=now()
      where wa_account_id=:id
      returning wa_account_id
    """),{"id":wa_account_id})
    return result.first() is not None

async def transport_status(db: AsyncSession) -> list[dict[str, Any]]:
    from app.services.transport_registry import get_whatsapp_transport
    rows=(await db.execute(text("""
      select id,account_key,label,transport,status,paired_at,revoked_at
      from wa_accounts
      where revoked_at is null
      order by created_at desc
    """))).mappings().all()
    transport=get_whatsapp_transport()
    result=[]
    for r in rows:
        item={
            'wa_account_id':str(r['id']), 'account_key':r['account_key'],
            'label':r['label'], 'transport':r['transport'], 'account_status':r['status'],
            'paired_at':_iso(r['paired_at']), 'revoked_at':_iso(r['revoked_at'])
        }
        try:
            item['operator']=await transport.status(r['account_key'])
            item['operator_error']=None
        except Exception as exc:
            item['operator']=None
            item['operator_error']=str(exc)[:1000]
        result.append(item)
    return result
