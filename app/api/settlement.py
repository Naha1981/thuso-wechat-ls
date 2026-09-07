from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.services.settlement import settle_payment, hold_provider_reserve, release_reserve, payout_with_reservation, SettlementError

router=APIRouter(prefix='/settlements',tags=['settlements'])
class SettleIn(BaseModel): provider_id: UUID; platform_fee: Decimal|None=Field(default=None,ge=0)
class ReserveIn(BaseModel): provider_id: UUID; payment_id: UUID; amount: Decimal=Field(gt=0); currency: str=Field(default='LSL',min_length=3,max_length=3)
@router.post('/payments/{payment_id}')
async def settle(payment_id:UUID, body:SettleIn, db:AsyncSession=Depends(get_db)):
 try: row=await settle_payment(db,payment_id,body.provider_id,body.platform_fee); await db.commit(); return row
 except SettlementError as e: await db.rollback(); raise HTTPException(409,str(e))
@router.post('/reserves')
async def reserve(body:ReserveIn, db:AsyncSession=Depends(get_db)):
 try: row=await hold_provider_reserve(db,body.provider_id,body.payment_id,body.amount,body.currency); await db.commit(); return row
 except SettlementError as e: await db.rollback(); raise HTTPException(409,str(e))
@router.post('/reserves/{reserve_id}/release')
async def release(reserve_id:UUID, db:AsyncSession=Depends(get_db)):
 try: row=await release_reserve(db,reserve_id); await db.commit(); return row
 except SettlementError as e: await db.rollback(); raise HTTPException(409,str(e))
@router.post('/payouts/{payout_id}/prepare')
async def prepare_payout(payout_id:UUID, db:AsyncSession=Depends(get_db)):
 try: row=await payout_with_reservation(db,payout_id); await db.commit(); return row
 except SettlementError as e: await db.rollback(); raise HTTPException(409,str(e))
