from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.execution import create_offers
from app.services.outbox import enqueue

ACTION_TO_CATEGORY = {
    "ride": "ride",
    "mechanic": "mechanic",
    "handyman": "handyman",
    "food": "food",
}

class AgentExecutionError(Exception):
    pass

async def create_action(
    db: AsyncSession, *, user_id: UUID, session_id: UUID | None,
    action: str, payload: dict, risk: str, idempotency_key: str
) -> dict:
    row = (await db.execute(text("""
        insert into agent_actions(user_id,session_id,action,risk,status,payload,idempotency_key)
        values (:user_id,:session_id,:action,:risk,'pending',cast(:payload as jsonb),:key)
        on conflict(idempotency_key) do update set idempotency_key=excluded.idempotency_key
        returning id,user_id,session_id,action,risk,status,payload,idempotency_key
    """), {
        "user_id": user_id, "session_id": session_id, "action": action,
        "risk": risk, "payload": __import__("json").dumps(payload), "key": idempotency_key,
    })).mappings().one()
    return dict(row)

async def approve_and_execute(db: AsyncSession, *, action_id: UUID, user_id: UUID) -> dict:
    action = (await db.execute(text("""
        select * from agent_actions where id=:id and user_id=:uid for update
    """), {"id": action_id, "uid": user_id})).mappings().first()
    if not action:
        raise AgentExecutionError("action not found")
    if action["status"] != "pending":
        raise AgentExecutionError(f"action is {action['status']}")

    payload = action["payload"] or {}
    await db.execute(text("""
        update agent_actions set status='approved', approved_at=now() where id=:id
    """), {"id": action_id})
    await db.execute(text("""
        insert into agent_action_events(action_id,event_type,actor_user_id,payload)
        values(:id,'approved',:uid,'{}'::jsonb)
    """), {"id": action_id, "uid": user_id})

    try:
        if action["action"] == "create_service_request":
            result = await _execute_service_request(db, user_id, payload, action_id)
        elif action["action"] == "cancel_request":
            result = await _cancel_request(db, user_id, payload)
        else:
            raise AgentExecutionError("unsupported action")

        await db.execute(text("""
            update agent_actions set status='executed', result=cast(:result as jsonb), executed_at=now()
            where id=:id
        """), {"id": action_id, "result": __import__("json").dumps(result, default=str)})
        await db.execute(text("""
            insert into agent_action_events(action_id,event_type,actor_user_id,payload)
            values(:id,'executed',:uid,cast(:payload as jsonb))
        """), {"id": action_id, "uid": user_id, "payload": __import__("json").dumps(result, default=str)})
        await db.execute(text("""
            insert into agent_receipts(action_id,user_id,action,authority,result)
            values(:id,:uid,:action,'one_time_confirmation',cast(:result as jsonb))
        """), {"id": action_id, "uid": user_id, "action": action["action"], "result": __import__("json").dumps(result, default=str)})
        return result
    except Exception:
        await db.execute(text("update agent_actions set status='failed' where id=:id"), {"id": action_id})
        raise

async def _execute_service_request(db: AsyncSession, user_id: UUID, payload: dict, action_id: UUID) -> dict:
    category = payload.get("category")
    if category not in ACTION_TO_CATEGORY:
        raise AgentExecutionError("unsupported service category")
    lat, lng = payload.get("pickup_lat"), payload.get("pickup_lng")
    details = payload.get("details", "")
    if lat is None or lng is None:
        raise AgentExecutionError("pickup_lat and pickup_lng are required")

    row = (await db.execute(text("""
        insert into service_requests(user_id,category,status,pickup_lat,pickup_lng,payload)
        values(:uid,:category,'searching',:lat,:lng,cast(:payload as jsonb))
        returning id,status,category
    """), {"uid": user_id, "category": category, "lat": lat, "lng": lng,
            "payload": __import__("json").dumps({"details": details, "source": "agent", "action_id": str(action_id)})})).mappings().one()
    offers = await create_offers(db, row["id"], category, lat, lng)
    await enqueue(db, "service_request", row["id"], "service.request_created", {
        "category": category, "user_id": str(user_id), "offer_count": len(offers)
    })
    return {"service_request_id": row["id"], "status": "offered" if offers else "searching", "offers_created": len(offers)}

async def _cancel_request(db: AsyncSession, user_id: UUID, payload: dict) -> dict:
    request_id = payload.get("request_id")
    if not request_id:
        raise AgentExecutionError("request_id is required")
    row = (await db.execute(text("""
        update service_requests set status='cancelled', cancelled_at=now(), version=version+1
        where id=:id and user_id=:uid and status in ('searching','offered','accepted','in_progress')
        returning id,status
    """), {"id": request_id, "uid": user_id})).mappings().first()
    if not row:
        raise AgentExecutionError("request cannot be cancelled")
    return {"service_request_id": row["id"], "status": row["status"]}
