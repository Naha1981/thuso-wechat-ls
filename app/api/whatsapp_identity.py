from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.auth import require_session
from app.services.whatsapp_identity import create_pairing_session, get_pairing_status, cancel_pairing
from app.services.transport_registry import get_whatsapp_transport

router = APIRouter(prefix='/identity/whatsapp', tags=['whatsapp-identity'])

class PairIn(BaseModel):
    label: str | None = Field(default=None, max_length=120)

@router.post('/pair')
async def pair(payload: PairIn, session=Depends(require_session), db: AsyncSession=Depends(get_db)):
    result = await create_pairing_session(db, session=session, label=payload.label)
    await db.commit()
    try:
        await get_whatsapp_transport().start_account(result['account_key'])
    except Exception as exc:
        await db.rollback()
        raise HTTPException(502, f'WhatsApp operator unavailable: {exc}')
    return result

@router.get('/pair/{onboarding_id}')
async def pair_status(onboarding_id: uuid.UUID, session=Depends(require_session), db: AsyncSession=Depends(get_db)):
    result = await get_pairing_status(db, session=session, onboarding_id=onboarding_id)
    if not result:
        raise HTTPException(404, 'pairing session not found')
    await db.commit()
    # Return the QR as data only while pairing; consumers should render it client-side.
    return result

@router.post('/pair/{onboarding_id}/cancel')
async def pair_cancel(onboarding_id: uuid.UUID, session=Depends(require_session), db: AsyncSession=Depends(get_db)):
    try:
        await cancel_pairing(db, session=session, onboarding_id=onboarding_id)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return {'ok': True}
