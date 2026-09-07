from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.db import get_db
from app.core.auth import require_session
from app.core.principal import require_provider_access, require_request_access
from app.services.financial import *

router=APIRouter(prefix='/financial',tags=['financial'])
class QuoteIn(BaseModel):
 request_id: UUID; subtotal: Decimal = Field(gt=0); fee_rate: Decimal = Field(default=Decimal('0.10'), ge=0, le=1)
class AcceptQuoteIn(BaseModel): pass
class PaymentIn(BaseModel):
 amount: Decimal = Field(gt=0); reference: str = Field(min_length=3,max_length=120); request_id: UUID|None=None; currency: str=Field(default='ZAR',min_length=3,max_length=3); idempotency_key: str|None=Field(default=None,max_length=160)
class ProviderRefIn(BaseModel): provider_reference: str=Field(min_length=1,max_length=160)
class RefundIn(BaseModel): amount: Decimal=Field(gt=0); reason: str=Field(min_length=2,max_length=160)
class DisputeIn(BaseModel): request_id: UUID; payment_id: UUID|None=None; amount: Decimal=Field(ge=0); reason: str=Field(min_length=2,max_length=160); description: str|None=None
class PayoutIn(BaseModel): amount: Decimal=Field(gt=0); currency: str=Field(default='ZAR',min_length=3,max_length=3)

@router.post('/quotes')
async def quote(body: QuoteIn,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await require_request_access(db,body.request_id,session)
 try: row=await create_quote(db,session['user_id'],body.request_id,body.subtotal,body.fee_rate); await db.commit(); return row
 except FinancialError as e: await db.rollback(); raise HTTPException(422,str(e))

@router.post('/quotes/{quote_id}/accept')
async def accept(quote_id:UUID,body:AcceptQuoteIn,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 try: row=await accept_quote(db,quote_id,session['user_id']); await db.commit(); return row
 except FinancialError as e: await db.rollback(); raise HTTPException(409,str(e))

@router.post('/payments/intents')
async def intent(body:PaymentIn,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 if body.request_id: await require_request_access(db,body.request_id,session)
 try: row=await create_payment_intent(db,session['user_id'],body.amount,body.reference,body.request_id,body.currency,body.idempotency_key); await db.commit(); return row
 except FinancialError as e: await db.rollback(); raise HTTPException(422,str(e))

@router.post('/payments/{payment_id}/authorize')
async def authorize(payment_id:UUID,body:ProviderRefIn,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await _require_payment_owner_or_provider(db,payment_id,session)
 try: row=await authorize_payment(db,payment_id,body.provider_reference); await db.commit(); return row
 except FinancialError as e: await db.rollback(); raise HTTPException(409,str(e))

@router.post('/payments/{payment_id}/capture')
async def capture(payment_id:UUID,body:ProviderRefIn,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await _require_payment_owner_or_provider(db,payment_id,session)
 try: row=await capture_payment(db,payment_id,body.provider_reference); await db.commit(); return row
 except FinancialError as e: await db.rollback(); raise HTTPException(409,str(e))

@router.post('/payments/{payment_id}/refunds')
async def refund(payment_id:UUID,body:RefundIn,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await _require_payment_owner_or_provider(db,payment_id,session)
 try: row=await request_refund(db,payment_id,body.amount,body.reason); await db.commit(); return row
 except FinancialError as e: await db.rollback(); raise HTTPException(409,str(e))

@router.post('/refunds/{refund_id}/complete')
async def complete(refund_id:UUID,body:ProviderRefIn,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await _require_financial_role(db,session)
 try: row=await complete_refund(db,refund_id,body.provider_reference); await db.commit(); return row
 except FinancialError as e: await db.rollback(); raise HTTPException(409,str(e))

@router.post('/disputes')
async def dispute(body:DisputeIn,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await require_request_access(db,body.request_id,session)
 row=await open_dispute(db,session['user_id'],body.request_id,body.payment_id,body.amount,body.reason,body.description); await db.commit(); return row

@router.get('/providers/{provider_id}/balance')
async def balance_endpoint(provider_id:UUID,currency:str='ZAR',db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await require_provider_access(db,provider_id,session)
 return {'provider_id':str(provider_id),'currency':currency,'balance':str(await provider_available_balance(db,provider_id,currency))}

@router.post('/providers/{provider_id}/payouts')
async def payout(provider_id:UUID,body:PayoutIn,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await require_provider_access(db,provider_id,session)
 try: row=await request_payout(db,provider_id,body.amount,body.currency); await db.commit(); return row
 except FinancialError as e: await db.rollback(); raise HTTPException(409,str(e))

class ProviderPaymentIn(BaseModel):
 provider: str; channel: str; phone: str = Field(min_length=8,max_length=32); name: str|None=None; callback_url: str|None=None

@router.post('/payments/{payment_id}/initiate')
async def initiate_provider(payment_id:UUID, body:ProviderPaymentIn, db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await _require_payment_owner_or_provider(db,payment_id,session)
 from app.services.payment_provider_service import initiate_provider_payment, ProviderPaymentError
 try: row=await initiate_provider_payment(db,payment_id,body.provider,body.channel,body.phone,body.name,body.callback_url); await db.commit(); return row
 except (ProviderPaymentError,KeyError) as e: await db.rollback(); raise HTTPException(422,str(e))

async def _require_payment_owner_or_provider(db, payment_id, session):
 row=(await db.execute(text("select user_id,service_request_id from payments where id=:id"),{'id':payment_id})).mappings().first()
 if not row: raise HTTPException(404,'payment not found')
 if UUID(str(row['user_id'])) == UUID(str(session['user_id'])): return row
 if row['service_request_id']:
  req=(await db.execute(text("select accepted_provider_id from service_requests where id=:id"),{'id':row['service_request_id']})).scalar_one_or_none()
  if req:
   await require_provider_access(db,UUID(str(req)),session); return row
 raise HTTPException(403,'payment access denied')

async def _require_financial_role(db,session):
 from app.core.principal import require_role
 await require_role(db,session,{'admin','finance'})
