from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _clean(value: str, limit: int = 600) -> str:
    value = re.sub(r"\s+", " ", value.replace("\x00", " ")).strip()
    return value[:limit]


async def record_turn(db: AsyncSession, *, user_id: UUID, channel: str, text_value: str,
                      source_message_id: UUID | None = None) -> None:
    """Persist a lightweight context event. Raw conversation remains in conversation_messages."""
    await db.execute(text("""
        insert into conversation_context_events(user_id,channel,event_type,source_message_id,payload)
        values(:uid,:channel,'turn',:mid,cast(:payload as jsonb))
    """), {"uid": user_id, "channel": channel, "mid": source_message_id,
           "payload": json.dumps({"text": _clean(text_value, 1000)})})


async def recent_context(db: AsyncSession, *, user_id: UUID, channel: str = "whatsapp",
                         limit: int = 12) -> dict[str, Any]:
    """Return bounded, non-sensitive context for agent prompting/decision logic."""
    messages = (await db.execute(text("""
        select direction,message_type,body,created_at
        from conversation_messages
        where user_id=:uid and channel=:channel
        order by created_at desc limit :limit
    """), {"uid": user_id, "channel": channel, "limit": limit})).mappings().all()
    memories = (await db.execute(text("""
        select memory_type,memory_key,memory_value,confidence
        from conversation_memory
        where user_id=:uid and channel=:channel
          and (expires_at is null or expires_at>now())
        order by updated_at desc limit 30
    """), {"uid": user_id, "channel": channel})).mappings().all()
    summary = (await db.execute(text("""
        select summary,message_count,last_message_at
        from conversation_summaries
        where user_id=:uid and channel=:channel
    """), {"uid": user_id, "channel": channel})).mappings().first()
    return {
        "summary": dict(summary) if summary else None,
        "recent_messages": [dict(x) for x in reversed(messages)],
        "memories": [dict(x) for x in memories],
    }


async def upsert_memory(db: AsyncSession, *, user_id: UUID, channel: str,
                        memory_type: str, key: str, value: str,
                        source_message_id: UUID | None = None,
                        confidence: float = 1.0, expires_at: Any = None) -> None:
    if memory_type not in {"preference", "fact", "task_context"}:
        raise ValueError("unsupported memory type")
    if not key or not value:
        raise ValueError("memory key/value required")
    await db.execute(text("""
        insert into conversation_memory(user_id,channel,memory_type,memory_key,memory_value,source_message_id,confidence,expires_at)
        values(:uid,:channel,:type,:key,:value,:mid,:confidence,:expires)
        on conflict(user_id,channel,memory_type,memory_key) do update set
          memory_value=excluded.memory_value,
          source_message_id=excluded.source_message_id,
          confidence=excluded.confidence,
          expires_at=excluded.expires_at,
          updated_at=now()
    """), {"uid": user_id, "channel": channel, "type": memory_type,
           "key": _clean(key, 120), "value": _clean(value), "mid": source_message_id,
           "confidence": max(0, min(1, confidence)), "expires": expires_at})


async def refresh_summary(db: AsyncSession, *, user_id: UUID, channel: str = "whatsapp") -> None:
    """Create a deterministic bounded summary from recent turns; no model call required."""
    rows = (await db.execute(text("""
        select direction,body,created_at
        from conversation_messages
        where user_id=:uid and channel=:channel
        order by created_at desc limit 20
    """), {"uid": user_id, "channel": channel})).mappings().all()
    if not rows:
        return
    snippets = []
    for r in reversed(rows):
        body = _clean(r["body"] or "", 240)
        if body:
            snippets.append(f"{r['direction']}: {body}")
    summary = "\n".join(snippets)[-4000:]
    await db.execute(text("""
      insert into conversation_summaries(user_id,channel,summary,message_count,last_message_at)
      values(:uid,:channel,:summary,:count,:last)
      on conflict(user_id,channel) do update set
        summary=excluded.summary,message_count=excluded.message_count,
        last_message_at=excluded.last_message_at,updated_at=now()
    """), {"uid": user_id, "channel": channel, "summary": summary,
           "count": len(rows), "last": rows[0]["created_at"]})
