from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.services.payment_orchestration import initiate_routed_payment, verify_mopay_payment, PaymentOrchestrationError

router=APIRouter(prefix='/payments',tags=['payment-orchestration'])
class InitiatePaymentIn(BaseModel):
    phone: str = Field(min_length=8,max_length=20)
    name: str|None=None
    callback_url: str|None=None
@router.post('/{payment_id}/initiate')
async def initiate(payment_id:UUID, body:InitiatePaymentIn, db:AsyncSession=Depends(get_db)):
    try:
        result=await initiate_routed_payment(db,payment_id,body.phone,body.name,body.callback_url); await db.commit(); return result
    except Exception as e:
        await db.rollback(); raise HTTPException(422,str(e))
@router.post('/{payment_id}/verify/mopay')
async def verify_mopay(payment_id:UUID, db:AsyncSession=Depends(get_db)):
    try:
        result=await verify_mopay_payment(db,payment_id); await db.commit(); return result
    except Exception as e:
        await db.rollback(); raise HTTPException(422,str(e))
