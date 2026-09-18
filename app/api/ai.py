from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import AIRequest
from app.ai.gateway import get_runtime_ai_provider
from app.core.auth import require_session
from app.core.db import get_db
from app.services.ai_usage import record_ai_usage

router = APIRouter(prefix="/ai", tags=["ai"])


class AIChatIn(BaseModel):
    messages: list[dict[str, str]] = Field(min_length=1, max_length=50)
    metadata: dict[str, str] = Field(default_factory=dict)
    channel: str = Field(default="api", max_length=30)


@router.get("/provider")
async def provider(session=Depends(require_session), db: AsyncSession = Depends(get_db)):
    _ = session
    ai = await get_runtime_ai_provider(db)
    return {
        "provider": ai.name,
        "capabilities": ai.capabilities(),
        "health": await ai.health(),
    }


@router.post("/chat")
async def chat(
    body: AIChatIn,
    session=Depends(require_session),
    db: AsyncSession = Depends(get_db),
):
    trace_id = uuid.uuid4()
    user_id = session["user_id"]

    try:
        from app.ai.contracts import AIMessage

        messages = [
            AIMessage(role=message["role"], content=message["content"])
            for message in body.messages
        ]
        result = await (await get_runtime_ai_provider(db)).chat(
            AIRequest(
                messages=messages,
                user_id=str(user_id),
                session_id=str(session.get("id")) if session.get("id") else None,
                trace_id=str(trace_id),
                metadata={**body.metadata, "channel": body.channel},
            )
        )

        await record_ai_usage(
            db,
            trace_id=trace_id,
            user_id=user_id,
            provider=result.provider,
            model=result.model,
            channel=body.channel,
            usage=result.usage or {},
            metadata=body.metadata,
        )
        await db.commit()

        return {
            "trace_id": trace_id,
            "provider": result.provider,
            "model": result.model,
            "content": result.content,
            "usage": result.usage,
        }
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=502, detail="AI provider request failed") from exc
