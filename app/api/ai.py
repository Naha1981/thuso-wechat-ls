from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import AIMessage, AIRequest
from app.ai.gateway import get_ai_provider
from app.core.db import get_db

router = APIRouter(prefix="/ai", tags=["ai"])


class AIChatIn(BaseModel):
    messages: list[AIMessage] = Field(min_length=1, max_length=50)
    user_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    metadata: dict = Field(default_factory=dict)


@router.get("/provider")
async def provider():
    ai = get_ai_provider()
    return {"provider": ai.name, "capabilities": ai.capabilities(), "health": await ai.health()}


@router.post("/chat")
async def chat(body: AIChatIn, db: AsyncSession = Depends(get_db)):
    _ = db  # reserved for usage/outcome metering
    trace_id = str(uuid.uuid4())
    try:
        result = await get_ai_provider().chat(
            AIRequest(
                messages=body.messages,
                user_id=str(body.user_id) if body.user_id else None,
                session_id=str(body.session_id) if body.session_id else None,
                trace_id=trace_id,
                metadata=body.metadata,
            )
        )
        return {
            "trace_id": trace_id,
            "provider": result.provider,
            "model": result.model,
            "content": result.content,
            "usage": result.usage,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
