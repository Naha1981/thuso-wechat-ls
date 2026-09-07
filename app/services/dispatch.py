from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from math import exp
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

@dataclass(frozen=True)
class Candidate:
    provider_id: UUID
    distance_m: float
    rating: float
    jobs_completed: int
    last_active_at: datetime | None
    response_rate: float = 0.0
    eta_seconds: int | None = None


def score_candidate(c: Candidate, now: datetime | None = None) -> float:
    """Deterministic dispatch score. Higher is better; weights are policy, not model output."""
    now = now or datetime.now(timezone.utc)
    distance_score = exp(-c.distance_m / 5000.0)
    rating_score = max(0.0, min(c.rating, 5.0)) / 5.0
    experience_score = min(max(c.jobs_completed, 0), 100) / 100.0
    response_score = max(0.0, min(c.response_rate, 1.0))
    freshness_score = 0.0
    if c.last_active_at:
        age = max(0.0, (now - c.last_active_at).total_seconds())
        freshness_score = exp(-age / 900.0)
    eta_score = exp(-max(c.eta_seconds or 0, 0) / 900.0) if c.eta_seconds is not None else 0.5
    return round(
        distance_score * 0.45
        + rating_score * 0.18
        + response_score * 0.15
        + freshness_score * 0.12
        + experience_score * 0.05
        + eta_score * 0.05,
        8,
    )


async def ranked_candidates(db: AsyncSession, category: str, lat: float, lng: float, radius_m: int = 15000, limit: int = 25):
    stmt = text("""
        SELECT p.id AS provider_id,
               ST_Distance(pl.location, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) AS distance_m,
               coalesce(p.rating,0) AS rating,
               coalesce(p.jobs_completed,0) AS jobs_completed,
               p.last_active_at,
               coalesce(p.response_rate,0) AS response_rate
        FROM providers p
        JOIN provider_locations pl ON pl.provider_id=p.id
        WHERE p.status='active' AND p.category=:category
          AND ST_DWithin(pl.location, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius)
        ORDER BY pl.location <-> ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography
        LIMIT :limit
    """)
    rows = (await db.execute(stmt, {"category":category,"lat":lat,"lng":lng,"radius":radius_m,"limit":limit})).mappings().all()
    candidates=[]
    for r in rows:
        c=Candidate(UUID(str(r['provider_id'])), float(r['distance_m']), float(r['rating']), int(r['jobs_completed']), r['last_active_at'], float(r['response_rate']))
        candidates.append({"provider_id":c.provider_id,"distance_m":c.distance_m,"score":score_candidate(c)})
    return sorted(candidates, key=lambda x: (-x['score'], x['distance_m']))


async def dispatch_wave(db: AsyncSession, request_id: UUID, category: str, lat: float | None, lng: float | None, wave_size: int = 5, radius_m: int = 15000):
    if lat is None or lng is None:
        return []
    candidates = await ranked_candidates(db, category, lat, lng, radius_m, max(wave_size * 3, wave_size))
    selected=[]
    for c in candidates:
        row=(await db.execute(text("""
          insert into service_offers(service_request_id,provider_id,status,expires_at,dispatch_score,dispatch_wave)
          values(:rid,:pid,'pending',now()+interval '2 minutes',:score,
                  coalesce((select max(dispatch_wave)+1 from service_offers where service_request_id=:rid),1))
          on conflict(service_request_id,provider_id) do nothing
          returning id,provider_id,expires_at,dispatch_score,dispatch_wave
        """), {"rid":request_id,"pid":c['provider_id'],"score":c['score']})).mappings().first()
        if row:
            selected.append(dict(row))
            if len(selected) >= wave_size:
                break
    if selected:
        await db.execute(text("update service_requests set status='offered',version=version+1 where id=:id and status in ('searching','offered')"), {"id":request_id})
        await db.execute(text("insert into dispatch_attempts(service_request_id,wave,candidate_count,offered_count,status) values(:rid,:wave,:c,:o,'sent')"), {"rid":request_id,"wave":selected[0]['dispatch_wave'],"c":len(candidates),"o":len(selected)})
    return selected


async def expire_offers(db: AsyncSession, request_id: UUID | None = None) -> int:
    where = "service_request_id=:rid and" if request_id else ""
    params = {"rid":request_id} if request_id else {}
    result = await db.execute(text(f"update service_offers set status='expired',responded_at=now() where {where} status='pending' and expires_at is not null and expires_at<=now()"), params)
    return result.rowcount or 0


async def reassign_if_needed(db: AsyncSession, request_id: UUID, category: str, lat: float | None, lng: float | None, wave_size: int = 5):
    await expire_offers(db, request_id)
    row=(await db.execute(text("select status from service_requests where id=:id for update"), {"id":request_id})).mappings().first()
    if not row or row['status'] != 'offered':
        return []
    pending=(await db.execute(text("select count(*) from service_offers where service_request_id=:id and status='pending' and expires_at>now()"), {"id":request_id})).scalar_one()
    if pending:
        return []
    await db.execute(text("update service_requests set status='searching',version=version+1 where id=:id"), {"id":request_id})
    return await dispatch_wave(db, request_id, category, lat, lng, wave_size)


async def update_provider_location(db: AsyncSession, provider_id: UUID, lat: float, lng: float, heading: float | None = None, speed_kmh: float | None = None):
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError('invalid coordinates')
    await db.execute(text("""
      insert into provider_locations(provider_id,location,heading,speed_kmh,updated_at)
      values(:pid,ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography,:heading,:speed,now())
      on conflict(provider_id) do update set location=excluded.location,heading=excluded.heading,speed_kmh=excluded.speed_kmh,updated_at=now()
    """), {'pid':provider_id,'lat':lat,'lng':lng,'heading':heading,'speed':speed_kmh})
    await db.execute(text("update providers set last_active_at=now() where id=:id"), {'id':provider_id})
