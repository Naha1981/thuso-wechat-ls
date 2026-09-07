from datetime import datetime
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.services.reconciliation import create_batch, match_item, close_batch, verify_destination, execute_payout, complete_payout, ReconciliationError

router=APIRouter(prefix='/reconciliation',tags=['reconciliation'])
class BatchIn(BaseModel): provider: str; currency: str=Field(min_length=3,max_length=3); period_start: datetime; period_end: datetime
class ItemIn(BaseModel): external_reference: str; amount: Decimal=Field(gt=0); currency: str=Field(min_length=3,max_length=3); external_status: str='paid'; metadata: dict={}
class DestinationIn(BaseModel): provider_id: UUID; rail: str; destination_ref: str; currency: str=Field(default='LSL',min_length=3,max_length=3)
class PayoutExecuteIn(BaseModel): rail: str; destination_ref: str
class PayoutCompleteIn(BaseModel): external_reference: str
@router.post('/batches')
async def batch(body:BatchIn,db:AsyncSession=Depends(get_db)):
 try: row=await create_batch(db,body.provider,body.currency,body.period_start,body.period_end); await db.commit(); return row
 except ReconciliationError as e: await db.rollback(); raise HTTPException(409,str(e))
@router.post('/batches/{batch_id}/items')
async def item(batch_id:UUID,body:ItemIn,db:AsyncSession=Depends(get_db)):
 try: row=await match_item(db,batch_id,body.external_reference,body.amount,body.currency,body.external_status,body.metadata); await db.commit(); return row
 except ReconciliationError as e: await db.rollback(); raise HTTPException(409,str(e))
@router.post('/batches/{batch_id}/close')
async def close(batch_id:UUID,db:AsyncSession=Depends(get_db)):
 try: row=await close_batch(db,batch_id); await db.commit(); return row
 except ReconciliationError as e: await db.rollback(); raise HTTPException(409,str(e))
@router.post('/payout-destinations')
async def destination(body:DestinationIn,db:AsyncSession=Depends(get_db)):
 try: row=await verify_destination(db,body.provider_id,body.rail,body.destination_ref,body.currency); await db.commit(); return row
 except ReconciliationError as e: await db.rollback(); raise HTTPException(409,str(e))
@router.post('/payouts/{payout_id}/execute')
async def payout(payout_id:UUID,body:PayoutExecuteIn,db:AsyncSession=Depends(get_db)):
 try: row=await execute_payout(db,payout_id,body.rail,body.destination_ref); await db.commit(); return row
 except ReconciliationError as e: await db.rollback(); raise HTTPException(409,str(e))
@router.post('/payout-attempts/{attempt_id}/complete')
async def complete(attempt_id:UUID,body:PayoutCompleteIn,db:AsyncSession=Depends(get_db)):
 try: row=await complete_payout(db,attempt_id,body.external_reference); await db.commit(); return row
 except ReconciliationError as e: await db.rollback(); raise HTTPException(409,str(e))
