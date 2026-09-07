from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

class PaymentError(Exception): pass

async def create_payment(db: AsyncSession, user_id: UUID, amount: Decimal, reference: str, service_request_id: UUID | None = None, currency: str = 'ZAR'):
    row = (await db.execute(text("""
      insert into payments(user_id,service_request_id,reference,amount,currency,status)
      values (:user_id,:request_id,:reference,:amount,:currency,'pending')
      on conflict(reference) do update set reference=excluded.reference
      returning id,reference,status,amount,currency
    """), {"user_id":user_id,"request_id":service_request_id,"reference":reference,"amount":amount,"currency":currency})).mappings().one()
    return dict(row)

async def mark_paid(db: AsyncSession, payment_id: UUID, provider_reference: str | None = None):
    row=(await db.execute(text("""
      update payments set status='paid', provider_reference=coalesce(:provider_reference,provider_reference), updated_at=now()
      where id=:id and status in ('pending','authorized') returning *
    """), {"id":payment_id,"provider_reference":provider_reference})).mappings().first()
    if not row: raise PaymentError('payment cannot be marked paid')
    return dict(row)

async def settle_verified_payment(db: AsyncSession, payment_id: UUID, provider_reference: str):
    from app.services.ledger_v2 import get_or_create_user_account, post_entry
    row=(await db.execute(text("select id,user_id,service_request_id,amount,currency,status,reference from payments where id=:id for update"),{'id':payment_id})).mappings().first()
    if not row: raise PaymentError('payment not found')
    if row['status']=='paid': return dict(row)
    if row['status'] not in ('pending','authorized'): raise PaymentError('payment cannot be settled')
    paid=await mark_paid(db,payment_id,provider_reference)
    account=await get_or_create_user_account(db,row['user_id'],row['currency'])
    await post_entry(db,account,row['reference'],'debit',Decimal(str(row['amount'])),row['currency'],{'payment_id':str(payment_id),'provider_reference':provider_reference,'type':'payment_settlement'})
    if row['service_request_id']:
        assignment=(await db.execute(text("select accepted_provider_id from service_requests where id=:id"),{'id':row['service_request_id']})).scalar_one_or_none()
        if assignment:
            from app.services.ledger_v2 import get_or_create_provider_account
            provider_account=await get_or_create_provider_account(db,assignment,row['currency'])
            await post_entry(db,provider_account,row['reference'], 'credit',Decimal(str(row['amount'])),row['currency'],{'payment_id':str(payment_id),'type':'provider_earning'})
            await db.execute(text("insert into provider_earnings(provider_id,service_request_id,amount,currency,status,reference) values(:pid,:rid,:amount,:currency,'available',:ref) on conflict(reference) do nothing"),{'pid':assignment,'rid':row['service_request_id'],'amount':row['amount'],'currency':row['currency'],'ref':f"earning:{row['reference']}"})
    commerce_order=(await db.execute(text("select id,merchant_id from commerce_orders where payment_id=:pid for update"),{'pid':payment_id})).mappings().first()
    if commerce_order:
        from app.services.commerce import mark_order_paid
        await mark_order_paid(db,payment_id)
    return paid
