from __future__ import annotations
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ACTIVE_REQUESTS = {"searching", "offered", "accepted", "in_progress"}

async def create_offers(db: AsyncSession, request_id: UUID, category: str, lat: float | None, lng: float | None, limit: int = 5):
    if lat is None or lng is None:
        return []
    sql = text("""
      insert into service_offers(service_request_id, provider_id, status, expires_at)
      select :request_id, p.id, 'pending', now() + interval '2 minutes'
      from providers p
      join provider_locations pl on pl.provider_id=p.id
      where p.status='active' and p.category=:category
        and ST_DWithin(pl.location, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius)
      order by pl.location <-> ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography
      limit :limit
      on conflict (service_request_id,provider_id) do nothing
      returning id, provider_id
    """)
    rows = (await db.execute(sql, {"request_id": request_id, "category": category, "lat": lat, "lng": lng, "radius": 15000, "limit": limit})).mappings().all()
    await db.execute(text("update service_requests set status='offered', version=version+1 where id=:id and status='searching'"), {"id": request_id})
    return [dict(r) for r in rows]

async def accept_offer(db: AsyncSession, offer_id: UUID, provider_id: UUID):
    offer = (await db.execute(text("""
      select id, service_request_id, provider_id, status from service_offers
      where id=:id for update
    """), {"id": offer_id})).mappings().first()
    if not offer or offer["provider_id"] != provider_id:
        raise ValueError("offer not found")
    if offer["status"] != "pending":
        raise ValueError("offer is no longer available")
    expiry=(await db.execute(text("select expires_at from service_offers where id=:id"), {"id": offer_id})).scalar_one()
    from datetime import datetime, timezone
    if expiry and expiry <= datetime.now(timezone.utc):
        await db.execute(text("update service_offers set status='expired',responded_at=now() where id=:id"), {"id": offer_id})
        raise ValueError("offer has expired")
    req = (await db.execute(text("select id,status,version from service_requests where id=:id for update"), {"id": offer["service_request_id"]})).mappings().first()
    if not req or req["status"] not in {"searching","offered"}:
        raise ValueError("request is no longer available")
    await db.execute(text("update service_offers set status='accepted',responded_at=now() where id=:id"), {"id": offer_id})
    await db.execute(text("""
      update service_offers set status='rejected', responded_at=now()
      where service_request_id=:rid and id<>:oid and status='pending'
    """), {"rid": offer["service_request_id"], "oid": offer_id})
    await db.execute(text("""
      update service_requests set status='accepted', accepted_provider_id=:pid, version=version+1
      where id=:rid
    """), {"rid": offer["service_request_id"], "pid": provider_id})
    return offer["service_request_id"]

async def transition_request(db: AsyncSession, request_id: UUID, new_status: str):
    allowed = {
      "accepted": {"in_progress","cancelled"},
      "in_progress": {"completed","cancelled"},
      "offered": {"cancelled"},
      "searching": {"cancelled"},
    }
    row = (await db.execute(text("select status from service_requests where id=:id for update"), {"id": request_id})).mappings().first()
    if not row: raise ValueError("request not found")
    if new_status not in allowed.get(row["status"], set()): raise ValueError(f"cannot transition {row['status']} to {new_status}")
    extras = "cancelled_at=now()," if new_status == "cancelled" else "completed_at=now()," if new_status == "completed" else ""
    await db.execute(text(f"update service_requests set status=:status, version=version+1, {extras} where id=:id"), {"id": request_id, "status": new_status})
