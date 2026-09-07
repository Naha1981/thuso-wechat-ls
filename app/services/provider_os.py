from __future__ import annotations
import re
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.execution import accept_offer, transition_request
from app.services.outbox import enqueue_channel, enqueue

CATEGORY_ALIASES = {
    'mechanic':'mechanic', 'mechanics':'mechanic', 'car mechanic':'mechanic',
    'handyman':'handyman', 'plumber':'plumber', 'electrician':'electrician',
    'cleaner':'cleaner', 'cleaning':'cleaner', 'delivery':'delivery', 'driver':'ride',
    'ride':'ride', 'food':'food', 'restaurant':'food', 'tutor':'tutor'
}

async def start_onboarding(db: AsyncSession, user_id: UUID, category: str | None = None, business_name: str | None = None):
    existing = (await db.execute(text("""select id,status,category,business_name from provider_onboarding_sessions
        where owner_user_id=:uid and status='collecting' and expires_at>now() order by created_at desc limit 1"""), {'uid':user_id})).mappings().first()
    if existing:
        sid=existing['id']
    else:
        sid=(await db.execute(text("insert into provider_onboarding_sessions(owner_user_id) values(:uid) returning id"), {'uid':user_id})).scalar_one()
    if category:
        category = CATEGORY_ALIASES.get(category.lower().strip(), category.lower().strip()[:40])
        await db.execute(text("update provider_onboarding_sessions set category=:c,updated_at=now() where id=:id"), {'c':category,'id':sid})
    if business_name:
        await db.execute(text("update provider_onboarding_sessions set business_name=:b,updated_at=now() where id=:id"), {'b':business_name.strip()[:160],'id':sid})
    row=(await db.execute(text("select id,category,business_name from provider_onboarding_sessions where id=:id"),{'id':sid})).mappings().one()
    if not row['category']:
        return {'status':'collecting','prompt':'Reply: PROVIDER <category> <business name>\nExample: PROVIDER electrician Acme Electrical'}
    if not row['business_name']:
        return {'status':'collecting','prompt':'What is your business/service name? Reply: BUSINESS <name>'}
    await db.execute(text("update provider_onboarding_sessions set status='submitted',updated_at=now() where id=:id"), {'id':sid})
    provider=(await db.execute(text("""insert into providers(owner_user_id,category,business_name,status,phone_e164,last_active_at)
      select owner_user_id,category,business_name,'pending',u.phone_e164,now() from provider_onboarding_sessions s join users u on u.id=s.owner_user_id
      where s.id=:id
      on conflict (phone_e164) do update set category=excluded.category,business_name=excluded.business_name
      returning id,category,business_name,status"""), {'id':sid})).mappings().one()
    await enqueue(db,'provider',provider['id'],'provider.onboarding_submitted',{'provider_id':str(provider['id'])})
    return {'status':'submitted','provider':dict(provider),'prompt':'Application submitted. Your provider account is pending verification.'}

async def get_provider_by_phone(db: AsyncSession, phone: str):
    return (await db.execute(text("select * from providers where phone_e164=:phone limit 1"), {'phone':phone})).mappings().first()

async def provider_offers(db: AsyncSession, provider_id: UUID):
    rows=(await db.execute(text("""select o.id,o.service_request_id,o.status,o.quoted_amount,o.eta_seconds,o.expires_at,
      r.category,r.pickup_lat,r.pickup_lng,r.payload,r.created_at
      from service_offers o join service_requests r on r.id=o.service_request_id
      where o.provider_id=:pid and o.status='pending' and (o.expires_at is null or o.expires_at>now())
      order by o.created_at desc limit 10"""),{'pid':provider_id})).mappings().all()
    return [dict(x) for x in rows]

async def provider_accept(db: AsyncSession, provider_id: UUID, offer_id: UUID):
    request_id=await accept_offer(db,offer_id,provider_id)
    await db.execute(text("update providers set last_active_at=now() where id=:id"),{'id':provider_id})
    await enqueue(db,'service_request',request_id,'service.provider_accepted',{'provider_id':str(provider_id),'offer_id':str(offer_id)})
    return request_id

async def provider_transition(db: AsyncSession, provider_id: UUID, request_id: UUID, status: str):
    row=(await db.execute(text("select accepted_provider_id from service_requests where id=:id for update"),{'id':request_id})).mappings().first()
    if not row or row['accepted_provider_id'] != provider_id: raise ValueError('provider is not assigned to this request')
    await transition_request(db,request_id,status)
    await db.execute(text("update providers set last_active_at=now(), jobs_completed=case when :status='completed' then jobs_completed+1 else jobs_completed end where id=:id"),{'id':provider_id,'status':status})
    await enqueue(db,'service_request',request_id,f'service.provider_{status}',{'provider_id':str(provider_id)})
    return request_id

async def record_earning(db: AsyncSession, provider_id: UUID, request_id: UUID, amount: Decimal, reference: str):
    row=await db.execute(text("""insert into provider_earnings(provider_id,service_request_id,amount,reference,status)
      values(:pid,:rid,:amount,:ref,'available') on conflict(reference) do nothing returning id"""),{'pid':provider_id,'rid':request_id,'amount':amount,'ref':reference})
    return row.scalar_one_or_none()

async def provider_earnings_summary(db: AsyncSession, provider_id: UUID):
    row=(await db.execute(text("""select count(*)::int as jobs, coalesce(sum(amount),0) as total,
      coalesce(sum(amount) filter(where status='available'),0) as available,
      coalesce(sum(amount) filter(where status='paid'),0) as paid
      from provider_earnings where provider_id=:pid"""),{'pid':provider_id})).mappings().one()
    return dict(row)

async def provider_reject(db: AsyncSession, provider_id: UUID, offer_id: UUID):
    row=(await db.execute(text("update service_offers set status='rejected',responded_at=now() where id=:oid and provider_id=:pid and status='pending' returning service_request_id"),{'oid':offer_id,'pid':provider_id})).mappings().first()
    if not row: raise ValueError('offer is no longer available')
    await db.execute(text("update providers set last_active_at=now() where id=:id"),{'id':provider_id})
    return row['service_request_id']

async def set_online(db: AsyncSession, provider_id: UUID, online: bool):
    status='active' if online else 'paused'
    row=(await db.execute(text("update providers set status=:status,last_active_at=now() where id=:id returning id,status"),{'id':provider_id,'status':status})).mappings().first()
    if not row: raise ValueError('provider not found')
    return dict(row)

def parse_provider_command(text_in: str) -> tuple[str, dict] | None:
    s=(text_in or '').strip()
    upper=s.upper()
    if upper.startswith('PROVIDER '):
        rest=s[9:].strip(); parts=rest.split(None,1)
        if len(parts)>=2: return 'onboard',{'category':parts[0].lower(),'business_name':parts[1]}
        return 'onboard',{}
    if upper.startswith('BUSINESS '): return 'business',{'business_name':s[9:].strip()}
    if upper in {'JOBS','MY JOBS','OFFERS'}: return 'offers',{}
    m=re.match(r'^(ACCEPT|TAKE)\s+([0-9a-fA-F-]{36})$',s,re.I)
    if m: return 'accept',{'offer_id':m.group(2)}
    m=re.match(r'^(REJECT|DECLINE)\s+([0-9a-fA-F-]{36})$',s,re.I)
    if m: return 'reject',{'offer_id':m.group(2)}
    m=re.match(r'^(START|BEGIN)\s+([0-9a-fA-F-]{36})$',s,re.I)
    if m: return 'start',{'request_id':m.group(2)}
    m=re.match(r'^(COMPLETE|DONE)\s+([0-9a-fA-F-]{36})(?:\s+(\d+(?:\.\d{1,2})?))?$',s,re.I)
    if m: return 'complete',{'request_id':m.group(2),'amount':m.group(3)}
    if upper in {'EARNINGS','BALANCE'}: return 'earnings',{}
    if upper in {'PAUSE','GO OFFLINE'}: return 'pause',{}
    if upper in {'ONLINE','GO ONLINE'}: return 'online',{}
    return None
