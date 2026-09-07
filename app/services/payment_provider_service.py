from __future__ import annotations
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.payments.registry import get_payment_registry
from app.payments.providers.base import PaymentRequest, PaymentCustomer

class ProviderPaymentError(Exception): pass

async def initiate_provider_payment(db: AsyncSession, payment_id: UUID, provider_name: str, channel: str, phone: str, name: str|None=None, callback_url: str|None=None):
    payment=(await db.execute(text('select * from payments where id=:id for update'),{'id':payment_id})).mappings().first()
    if not payment: raise ProviderPaymentError('payment not found')
    if payment['status'] not in ('pending','authorized'): raise ProviderPaymentError('payment is not payable')
    provider=get_payment_registry().get(provider_name)
    if channel not in provider.channels: raise ProviderPaymentError('channel is not supported by provider')
    result=await provider.initiate(PaymentRequest(str(payment_id),Decimal(str(payment['amount'])),payment['currency'],payment['reference'],PaymentCustomer(str(payment['user_id']),phone,name),callback_url))
    await db.execute(text('''update payments set provider=:provider,channel=:channel,provider_reference=coalesce(:pref,provider_reference),checkout_url=:url,initiated_at=now(),updated_at=now() where id=:id'''),{'provider':provider_name,'channel':channel,'pref':result.provider_reference,'url':result.checkout_url,'id':payment_id})
    return {'payment_id':str(payment_id),'provider':provider_name,'channel':channel,'status':result.status,'provider_reference':result.provider_reference,'checkout_url':result.checkout_url,'raw':result.raw}

async def process_provider_webhook(db: AsyncSession, provider_name: str, event: dict):
    external_event_id=str(event.get('event_id') or event.get('id') or event.get('reference') or '')
    if not external_event_id: raise ProviderPaymentError('webhook missing event id')
    payment_ref=event.get('payment_id') or event.get('merchant_reference') or event.get('reference')
    status=str(event.get('status','')).lower()
    inserted=(await db.execute(text('''insert into payment_events(provider,external_event_id,event_type,status,payload) values(:p,:eid,:type,'received',cast(:payload as jsonb)) on conflict(provider,external_event_id) do nothing returning id'''),{'p':provider_name,'eid':external_event_id,'type':str(event.get('type','payment.updated')),'payload':__import__('json').dumps(event)})).scalar_one_or_none()
    if not inserted: return {'duplicate':True,'external_event_id':external_event_id}
    if not payment_ref: raise ProviderPaymentError('webhook missing payment reference')
    row=(await db.execute(text('select id,status from payments where id::text=:ref or reference=:ref or provider_reference=:ref for update'),{'ref':str(payment_ref)})).mappings().first()
    if not row: raise ProviderPaymentError('payment not found')
    mapping={'success':'paid','succeeded':'paid','paid':'paid','captured':'paid','authorized':'authorized','pending':'pending','failed':'failed','cancelled':'cancelled','canceled':'cancelled'}
    target=mapping.get(status)
    if target:
        await db.execute(text('''update payments set status=:status, captured_at=case when :status='paid' then coalesce(captured_at,now()) else captured_at end, updated_at=now() where id=:id'''),{'status':target,'id':row['id']})
    await db.execute(text("update payment_events set status='processed',processed_at=now(),payment_id=:pid where id=:eid"),{'pid':row['id'],'eid':inserted})
    return {'duplicate':False,'payment_id':str(row['id']),'status':target or status,'external_event_id':external_event_id}
