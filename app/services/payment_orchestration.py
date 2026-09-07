from __future__ import annotations
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.payments.registry import get_payment_registry
from app.services.payment_provider_service import initiate_provider_payment, ProviderPaymentError
from app.services.payment_routing import choose_route, RouteCandidate

class PaymentOrchestrationError(Exception): pass

async def initiate_routed_payment(db: AsyncSession, payment_id: UUID, phone: str, name: str|None=None, callback_url: str|None=None):
    p=(await db.execute(text('select id,user_id,amount,currency,reference,status from payments where id=:id for update'),{'id':payment_id})).mappings().first()
    if not p: raise PaymentOrchestrationError('payment not found')
    if p['status'] not in ('pending','authorized'): raise PaymentOrchestrationError('payment is not payable')
    rows=(await db.execute(text('''select provider,channel,fee_fixed,fee_rate,priority,max_amount,enabled,health_status,supports_refund,supports_payout
      from payment_route_policies where country_code='LS' and currency=:currency and enabled=true'''),{'currency':p['currency']})).mappings().all()
    candidates=[RouteCandidate(r['provider'],r['channel'],Decimal(str(r['fee_fixed'])),Decimal(str(r['fee_rate'])),int(r['priority']),r['health_status']!='down',r['enabled'],r['supports_refund'],r['supports_payout'],Decimal(str(r['max_amount'])) if r['max_amount'] is not None else None) for r in rows]
    decision=choose_route(Decimal(str(p['amount'])),candidates)
    await db.execute(text('''insert into payment_route_decisions(payment_id,country_code,currency,amount,selected_provider,selected_channel,estimated_fee,score,fallbacks,reason)
      values(:pid,'LS',:currency,:amount,:provider,:channel,:fee,:score,cast(:fallbacks as jsonb),:reason)'''),{'pid':payment_id,'currency':p['currency'],'amount':p['amount'],'provider':decision.provider,'channel':decision.channel,'fee':decision.estimated_fee,'score':decision.score,'fallbacks':__import__('json').dumps(list(decision.fallback_providers)),'reason':decision.reason})
    result=await initiate_provider_payment(db,payment_id,decision.provider,decision.channel,phone,name,callback_url)
    await db.execute(text('''insert into payment_attempts(payment_id,provider,channel,attempt_no,status,provider_reference,checkout_url,created_at)
      values(:pid,:provider,:channel,(select coalesce(max(attempt_no),0)+1 from payment_attempts where payment_id=:pid),:status,:pref,:url,now())'''),{'pid':payment_id,'provider':decision.provider,'channel':decision.channel,'status':result['status'],'pref':result.get('provider_reference'),'url':result.get('checkout_url')})
    return {**result,'fallbacks':list(decision.fallback_providers),'estimated_fee':str(decision.estimated_fee)}

async def verify_mopay_payment(db: AsyncSession, payment_id: UUID):
    p=(await db.execute(text('select id,provider_reference,status from payments where id=:id for update'),{'id':payment_id})).mappings().first()
    if not p: raise PaymentOrchestrationError('payment not found')
    if p['provider_reference'] is None: raise PaymentOrchestrationError('provider session missing')
    adapter=get_payment_registry().get('mopay_ls')
    if not hasattr(adapter,'get_status'): raise PaymentOrchestrationError('provider does not support status verification')
    data=await adapter.get_status(str(p['provider_reference']))
    session=data.get('session',data)
    status=str(session.get('transactionStatus') or session.get('status') or '').lower()
    mapping={'success':'paid','succeeded':'paid','completed':'paid','paid':'paid','failed':'failed','cancelled':'cancelled','canceled':'cancelled','pending':'pending'}
    target=mapping.get(status)
    if target:
        await db.execute(text("update payments set status=:status,captured_at=case when :status='paid' then coalesce(captured_at,now()) else captured_at end,updated_at=now() where id=:id"),{'status':target,'id':payment_id})
    return {'payment_id':str(payment_id),'provider':'mopay_ls','status':target or status,'verified':True,'raw':data}
