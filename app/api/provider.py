from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.services.provider_os import provider_offers, provider_accept, provider_reject, provider_transition, provider_earnings_summary, start_onboarding, set_online
from app.services.outbox import enqueue

router=APIRouter(prefix='/providers',tags=['providers'])

async def require_internal(x_internal_secret: str|None=Header(default=None), db: AsyncSession=Depends(get_db)):
    from app.core.config import get_settings
    secret=get_settings().internal_webhook_secret
    if not secret or x_internal_secret != secret: raise HTTPException(401,'provider API requires authenticated provider session')
    return db

@router.post('/{provider_id}/onboarding/submit')
async def submit(provider_id: UUID, db: AsyncSession=Depends(require_internal)):
    row=(await db.execute(text("update providers set status='pending',last_active_at=now() where id=:id returning id,status"),{'id':provider_id})).mappings().first()
    if not row: raise HTTPException(404,'provider not found')
    await enqueue(db,'provider',provider_id,'provider.verification_required',{'provider_id':str(provider_id)})
    await db.commit(); return dict(row)

@router.get('/{provider_id}/offers')
async def offers(provider_id: UUID, db: AsyncSession=Depends(require_internal)): return {'offers':await provider_offers(db,provider_id)}

@router.post('/{provider_id}/offers/{offer_id}/accept')
async def accept(provider_id: UUID, offer_id: UUID, db: AsyncSession=Depends(require_internal)):
    try: rid=await provider_accept(db,provider_id,offer_id)
    except ValueError as e: raise HTTPException(409,str(e))
    await db.commit(); return {'request_id':rid,'status':'accepted'}

@router.post('/{provider_id}/offers/{offer_id}/reject')
async def reject(provider_id: UUID, offer_id: UUID, db: AsyncSession=Depends(require_internal)):
    try: rid=await provider_reject(db,provider_id,offer_id)
    except ValueError as e: raise HTTPException(409,str(e))
    await db.commit(); return {'request_id':rid,'status':'rejected'}

@router.post('/{provider_id}/presence/{mode}')
async def presence(provider_id: UUID, mode: str, db: AsyncSession=Depends(require_internal)):
    if mode not in {'online','offline'}: raise HTTPException(422,'mode must be online or offline')
    try: row=await set_online(db,provider_id,mode=='online')
    except ValueError as e: raise HTTPException(404,str(e))
    await db.commit(); return row

@router.post('/{provider_id}/requests/{request_id}/{status}')
async def transition(provider_id: UUID, request_id: UUID, status: str, db: AsyncSession=Depends(require_internal)):
    if status not in {'in_progress','completed','cancelled'}: raise HTTPException(422,'invalid status')
    try: await provider_transition(db,provider_id,request_id,status)
    except ValueError as e: raise HTTPException(409,str(e))
    await db.commit(); return {'request_id':request_id,'status':status}

@router.get('/{provider_id}/earnings')
async def earnings(provider_id: UUID, db: AsyncSession=Depends(require_internal)): return await provider_earnings_summary(db,provider_id)
