from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal('0.01')

def money(v: Decimal | int | float | str) -> Decimal:
    return Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_UP)

class FinancialError(Exception): pass

async def create_quote(db: AsyncSession, user_id: UUID, request_id: UUID, subtotal: Decimal, fee_rate: Decimal = Decimal('0.10'), ttl_seconds: int = 300):
    subtotal = money(subtotal)
    if subtotal <= 0: raise FinancialError('subtotal must be positive')
    fee = money(subtotal * fee_rate)
    provider = money(subtotal - fee)
    total = subtotal
    if provider < 0: raise FinancialError('invalid pricing')
    row=(await db.execute(text('''
      insert into pricing_quotes(service_request_id,user_id,subtotal,platform_fee,provider_earning,total,expires_at)
      values(:rid,:uid,:subtotal,:fee,:earning,:total,now()+make_interval(secs=>:ttl))
      returning *
    '''), {'rid':request_id,'uid':user_id,'subtotal':subtotal,'fee':fee,'earning':provider,'total':total,'ttl':ttl_seconds})).mappings().one()
    return dict(row)

async def accept_quote(db: AsyncSession, quote_id: UUID, user_id: UUID):
    row=(await db.execute(text('''
      update pricing_quotes set status='accepted',accepted_at=now()
      where id=:id and user_id=:uid and status='quoted' and expires_at>now()
      returning *
    '''), {'id':quote_id,'uid':user_id})).mappings().first()
    if not row: raise FinancialError('quote unavailable')
    return dict(row)

async def enforce_risk_limit(db: AsyncSession, user_id: UUID, amount: Decimal):
    amount=money(amount)
    row=(await db.execute(text('select max_transaction_amount,max_daily_amount,max_daily_count,enabled from financial_risk_limits where scope=\'default\''))).mappings().one()
    if not row['enabled']: return
    if amount > row['max_transaction_amount']: raise FinancialError('transaction exceeds maximum')
    daily=(await db.execute(text('''
      select coalesce(sum(amount),0) total, count(*) count from payments
      where user_id=:uid and created_at>=current_date and status not in ('failed','cancelled')
    '''), {'uid':user_id})).mappings().one()
    if Decimal(str(daily['total'])) + amount > row['max_daily_amount']: raise FinancialError('daily transaction limit exceeded')
    if int(daily['count']) >= row['max_daily_count']: raise FinancialError('daily transaction count exceeded')

async def create_payment_intent(db: AsyncSession, user_id: UUID, amount: Decimal, reference: str, request_id: UUID|None=None, currency='ZAR', idempotency_key: str|None=None):
    amount=money(amount)
    await enforce_risk_limit(db,user_id,amount)
    row=(await db.execute(text('''
      insert into payments(user_id,service_request_id,reference,amount,currency,status,idempotency_key)
      values(:uid,:rid,:ref,:amount,:currency,'pending',:key)
      on conflict(reference) do update set reference=excluded.reference
      returning *
    '''), {'uid':user_id,'rid':request_id,'ref':reference,'amount':amount,'currency':currency,'key':idempotency_key})).mappings().one()
    return dict(row)

async def authorize_payment(db: AsyncSession, payment_id: UUID, provider_reference: str):
    row=(await db.execute(text('''
      update payments set status='authorized',provider_reference=:ref,authorized_at=now(),updated_at=now()
      where id=:id and status='pending' returning *
    '''), {'id':payment_id,'ref':provider_reference})).mappings().first()
    if not row: raise FinancialError('payment cannot be authorized')
    return dict(row)

async def capture_payment(db: AsyncSession, payment_id: UUID, provider_reference: str):
    row=(await db.execute(text('''
      update payments set status='paid',provider_reference=coalesce(:ref,provider_reference),captured_at=now(),updated_at=now()
      where id=:id and status in ('authorized','pending') returning *
    '''), {'id':payment_id,'ref':provider_reference})).mappings().first()
    if not row: raise FinancialError('payment cannot be captured')
    return dict(row)

async def request_refund(db: AsyncSession, payment_id: UUID, amount: Decimal, reason: str):
    amount=money(amount)
    payment=(await db.execute(text('select id,user_id,amount,currency,status,refunded_amount from payments where id=:id for update'),{'id':payment_id})).mappings().first()
    if not payment: raise FinancialError('payment not found')
    if payment['status'] != 'paid': raise FinancialError('payment is not refundable')
    remaining=money(Decimal(str(payment['amount']))-Decimal(str(payment['refunded_amount'])) )
    if amount > remaining: raise FinancialError('refund exceeds remaining payment')
    ref=f'refund:{payment_id}:{uuid4()}'
    row=(await db.execute(text('''insert into refunds(payment_id,user_id,amount,currency,status,reference,reason)
      values(:pid,:uid,:amount,:currency,'requested',:ref,:reason) returning *'''), {'pid':payment_id,'uid':payment['user_id'],'amount':amount,'currency':payment['currency'],'ref':ref,'reason':reason})).mappings().one()
    return dict(row)

async def complete_refund(db: AsyncSession, refund_id: UUID, provider_reference: str):
    refund=(await db.execute(text('select * from refunds where id=:id for update'),{'id':refund_id})).mappings().first()
    if not refund: raise FinancialError('refund not found')
    if refund['status']=='succeeded': return dict(refund)
    if refund['status']!='requested': raise FinancialError('refund cannot be completed')
    row=(await db.execute(text('''update refunds set status='succeeded',provider_reference=:ref,processed_at=now()
      where id=:id returning *'''),{'id':refund_id,'ref':provider_reference})).mappings().one()
    await db.execute(text('update payments set refunded_amount=refunded_amount+:amount,status=case when refunded_amount+:amount>=amount then \'refunded\' else status end,updated_at=now() where id=:pid'),{'amount':refund['amount'],'pid':refund['payment_id']})
    return dict(row)

async def open_dispute(db: AsyncSession, user_id: UUID, request_id: UUID, payment_id: UUID|None, amount: Decimal, reason: str, description: str|None=None):
    row=(await db.execute(text('''insert into disputes(user_id,service_request_id,payment_id,amount,reason,description)
      values(:uid,:rid,:pid,:amount,:reason,:description) returning *'''), {'uid':user_id,'rid':request_id,'pid':payment_id,'amount':money(amount),'reason':reason,'description':description})).mappings().one()
    return dict(row)

async def provider_available_balance(db: AsyncSession, provider_id: UUID, currency='ZAR'):
    from app.services.ledger_v2 import get_or_create_provider_account, balance
    account=await get_or_create_provider_account(db,provider_id,currency)
    return await balance(db,account)

async def request_payout(db: AsyncSession, provider_id: UUID, amount: Decimal, currency='ZAR'):
    amount=money(amount)
    if amount<=0: raise FinancialError('amount must be positive')
    available=await provider_available_balance(db,provider_id,currency)
    if amount>available: raise FinancialError('insufficient available balance')
    ref=f'payout:{provider_id}:{uuid4()}'
    row=(await db.execute(text('''insert into provider_payouts(provider_id,amount,currency,status,reference) values(:pid,:amount,:currency,'requested',:ref) returning *'''), {'pid':provider_id,'amount':amount,'currency':currency,'ref':ref})).mappings().one()
    return dict(row)
