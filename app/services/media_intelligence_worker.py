from __future__ import annotations

import asyncio
import json
import os
import socket
from uuid import UUID

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings

STREAM = "naha:media:intelligence"
GROUP = "media-intelligence-workers"


def consumer_name() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


async def ensure_group(redis: Any) -> None:
    try:
        await redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def enqueue_pending(redis: Any, limit: int = 50) -> int:
    """Publish pending DB jobs to Redis without changing DB state.

    The database remains the durable source of truth. A periodic sweep makes the
    Redis stream self-healing if the API committed a job but Redis was unavailable.
    Duplicate stream entries are harmless because consumers re-check job state.
    """
    from app.core.db import SessionLocal
    async with SessionLocal() as db:
        rows = (await db.execute(text("""
            select id, media_id, job_type
            from media_processing_jobs
            where status='pending'
              and available_at<=now()
              and job_type in ('transcribe','understand','extract_document','extract_receipt')
            order by created_at
            limit :limit
        """), {"limit": limit})).mappings().all()
    count = 0
    for row in rows:
        await redis.xadd(STREAM, {
            "job_id": str(row["id"]),
            "media_id": str(row["media_id"]),
            "job_type": row["job_type"],
        }, maxlen=100_000, approximate=True)
        count += 1
    return count


async def claim_stream_job(job_id: UUID) -> dict | None:
    from app.core.db import SessionLocal
    async with SessionLocal() as db:
        row = (await db.execute(text("""
            update media_processing_jobs
               set status='processing', attempts=attempts+1, updated_at=now()
             where id=:id and status='pending' and available_at<=now()
         returning *
        """), {"id": job_id})).mappings().first()
        await db.commit()
        return dict(row) if row else None


async def handle_job(job: dict) -> None:
    claimed = await claim_stream_job(UUID(str(job["id"])))
    if not claimed:
        return
    try:
        from app.core.db import SessionLocal
        from app.services.media_intelligence import process_intelligence_job
        from app.services.outbox import enqueue_channel
        async with SessionLocal() as db:
            result = await process_intelligence_job(db, claimed)
            # Persist a compact, queryable context projection for the agent layer.
            await db.execute(text("""
                insert into media_intelligence_context(media_id,owner_user_id,task_type,text_content,structured,created_at)
                select m.id,m.owner_user_id,:task,:text,cast(:structured as jsonb),now()
                  from media_objects m
                 where m.id=:media_id
                on conflict(media_id,task_type) do update
                  set text_content=excluded.text_content,
                      structured=excluded.structured,
                      updated_at=now()
            """), {
                "media_id": claimed["media_id"],
                "task": result["task_type"],
                "text": result.get("text"),
                "structured": json.dumps(result.get("structured") or {}),
            })

            # Voice notes are conversational input. Feed the verified transcription
            # into the same agent core used by text messages. The agent may propose
            # consequential actions, but execution still requires the existing
            # confirmation/risk boundary.
            if result["task_type"] == "transcription" and (result.get("text") or "").strip():
                await bridge_transcription_to_agent(db, claimed, result)

            settings = get_settings()
            if settings.intelligence_auto_reply:
                owner = (await db.execute(text("""
                    select u.phone_e164
                    from media_objects m
                    join users u on u.id=m.owner_user_id
                    where m.id=:media_id
                """), {"media_id": claimed["media_id"]})).scalar_one_or_none()
                if owner:
                    body = _reply_text(result)
                    await enqueue_channel(db, "whatsapp", owner, "text", {"body": body})

            await db.commit()
    except Exception as exc:
        from app.core.db import SessionLocal
        # The processing session rolls back on provider failure, so persist retry state
        # in a fresh transaction. The DB sweep will republish the job.
        async with SessionLocal() as db:
            await db.execute(text("""
                update media_intelligence_results
                   set status='failed', error=:error, updated_at=now()
                 where media_id=:media_id and task_type=(
                   select case job_type
                     when 'transcribe' then 'transcription'
                     when 'understand' then 'vision'
                     when 'extract_document' then 'document'
                     when 'extract_receipt' then 'receipt'
                   end from media_processing_jobs where id=:job_id
                 )
            """), {"media_id": claimed["media_id"], "job_id": claimed["id"], "error": str(exc)[:2000]})
            await db.execute(text("""
                update media_processing_jobs
                   set status=case when attempts>=5 then 'failed' else 'pending' end,
                       last_error=:error,
                       available_at=now()+make_interval(secs=>least(300,power(2,attempts)::int*5)),
                       updated_at=now()
                 where id=:id
            """), {"id": claimed["id"], "error": str(exc)[:2000]})
            await db.commit()
        raise


async def bridge_transcription_to_agent(db: Any, job: dict, result: dict) -> dict:
    media_id = job["media_id"]
    row = (await db.execute(text("""
        select m.owner_user_id, m.external_message_id, u.phone_e164, r.id as result_id
          from media_objects m
          join users u on u.id=m.owner_user_id
          left join media_intelligence_results r
            on r.media_id=m.id and r.task_type='transcription'
         where m.id=:media_id
    """), {"media_id": media_id})).mappings().first()
    if not row or not row["owner_user_id"]:
        raise RuntimeError("media owner missing")
    text_value = str(result.get("text") or "").strip()[:4000]
    existing = (await db.execute(text("select id from media_agent_turns where media_id=:mid and source_task_type='transcription'"), {"mid": media_id})).scalar_one_or_none()
    if existing:
        return {"id": existing, "duplicate": True}
    await db.execute(text("""
      insert into media_agent_turns(media_id,owner_user_id,source_task_type,source_result_id,input_text,status)
      values(:mid,:uid,'transcription',:rid,:input,'processing')
      on conflict(media_id,source_task_type) do nothing
    """), {"mid": media_id, "uid": row["owner_user_id"], "rid": row["result_id"], "input": text_value})
    from app.api.agent import AgentMessageIn, process_message
    out = await process_message(AgentMessageIn(
        user_id=row["owner_user_id"], text=text_value, channel='whatsapp',
        external_message_id=f"media:{media_id}",
    ), db)
    action_id = out.actions[0].id if out.actions else None
    await db.execute(text("""
      update media_agent_turns
         set agent_reply=:reply,intent=:intent,confidence=:confidence,trace_id=:trace,action_id=:action,status='completed',updated_at=now()
       where media_id=:mid and source_task_type='transcription'
    """), {"reply": out.reply, "intent": out.intent, "confidence": out.confidence, "trace": out.trace_id, "action": action_id, "mid": media_id})
    # Deliver the agent's response through the normal channel outbox. If an action
    # exists, expose the same explicit Confirm/Decline buttons used for text input.
    from app.services.outbox import enqueue_channel
    payload = {"body": out.reply}
    if out.actions:
        payload["buttons"] = [
            {"id": f"agent:confirm:{out.actions[0].id}", "title": "Confirm"},
            {"id": f"agent:decline:{out.actions[0].id}", "title": "Decline"},
        ]
    await enqueue_channel(db, 'whatsapp', row["phone_e164"].lstrip('+'), 'buttons' if out.actions else 'text', payload)
    return {"trace_id": str(out.trace_id), "action_id": str(action_id) if action_id else None}

def _reply_text(result: dict) -> str:
    task = result["task_type"]
    text_value = (result.get("text") or "").strip()
    if task == "transcription":
        return f"I received your voice note. Here is the transcription:\n\n{text_value[:5900]}" if text_value else "I received your voice note, but I couldn't detect clear speech."
    if task == "receipt":
        fields = result.get("structured") or {}
        receipt = fields.get("receipt") or {}
        total = receipt.get("total")
        currency = receipt.get("currency")
        if total:
            return f"Receipt processed. Total: {currency + ' ' if currency else ''}{total}."
    return "I received and processed your media."


async def consume(redis: Any, name: str) -> None:
    while True:
        messages = await redis.xreadgroup(GROUP, name, {STREAM: ">"}, count=10, block=5000)
        for _, entries in messages:
            for stream_id, fields in entries:
                try:
                    await handle_job(fields)
                    await redis.xack(STREAM, GROUP, stream_id)
                except Exception:
                    # Do not ACK failures. Reclaim is handled by the pending DB sweep;
                    # keeping the entry also preserves an operational audit trail.
                    continue


async def run_forever() -> None:
    from redis.asyncio import Redis
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    name = consumer_name()
    try:
        await ensure_group(redis)
        while True:
            await enqueue_pending(redis)
            await asyncio.sleep(0.5)
    finally:
        await redis.aclose()


async def run_worker() -> None:
    from redis.asyncio import Redis
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    name = consumer_name()
    try:
        await ensure_group(redis)
        await asyncio.gather(consume(redis, name), _sweep(redis))
    finally:
        await redis.aclose()


async def _sweep(redis: Any) -> None:
    while True:
        await enqueue_pending(redis)
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(run_worker())
