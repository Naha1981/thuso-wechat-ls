from __future__ import annotations
import json
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.dispatch import dispatch_wave, update_provider_location
from app.services.outbox import enqueue, enqueue_channel

TRANSITIONS = {
    'searching': {'assigned','cancelled','failed'},
    'assigned': {'at_pickup','cancelled','failed'},
    'at_pickup': {'picked_up','cancelled','failed'},
    'picked_up': {'in_transit','cancelled','failed'},
    'in_transit': {'delivered','cancelled','failed'},
}

async def _event(db, job_id: UUID, event_type: str, actor_type: str, actor_id: UUID|None, payload: dict):
    await db.execute(text("""insert into delivery_events(delivery_job_id,event_type,actor_type,actor_id,payload)
      values(:jid,:etype,:atype,:aid,cast(:payload as jsonb))"""),
      {'jid':job_id,'etype':event_type,'atype':actor_type,'aid':actor_id,'payload':json.dumps(payload)})
    await enqueue(db,'delivery_job',job_id,f'delivery.{event_type}',payload)

async def create_delivery_job(db: AsyncSession, user_id: UUID, order_id: UUID, pickup_provider_id: UUID, pickup_lat: float, pickup_lng: float, dropoff_lat: float, dropoff_lng: float, delivery_fee: Decimal = Decimal('0')):
    existing=(await db.execute(text('select * from delivery_jobs where order_id=:oid'),{'oid':order_id})).mappings().first()
    if existing: return dict(existing)
    rid=(await db.execute(text("""insert into service_requests(user_id,category,status,pickup_lat,pickup_lng,payload)
      values(:uid,'delivery','searching',:plat,:plng,cast(:payload as jsonb)) returning id"""),
      {'uid':user_id,'plat':pickup_lat,'plng':pickup_lng,'payload':json.dumps({'order_id':str(order_id),'dropoff_lat':dropoff_lat,'dropoff_lng':dropoff_lng,'pickup_provider_id':str(pickup_provider_id)})})).scalar_one()
    job=(await db.execute(text("""insert into delivery_jobs(service_request_id,order_id,pickup_provider_id,pickup_lat,pickup_lng,dropoff_lat,dropoff_lng,delivery_fee)
      values(:rid,:oid,:pid,:plat,:plng,:dlat,:dlng,:fee) returning *"""),
      {'rid':rid,'oid':order_id,'pid':pickup_provider_id,'plat':pickup_lat,'plng':pickup_lng,'dlat':dropoff_lat,'dlng':dropoff_lng,'fee':delivery_fee})).mappings().one()
    await db.execute(text('update service_requests set delivery_job_id=:jid where id=:rid'),{'jid':job['id'],'rid':rid})
    offers=await dispatch_wave(db,rid,'delivery',pickup_lat,pickup_lng)
    await _event(db,job['id'],'created','system',None,{'order_id':str(order_id),'request_id':str(rid),'offer_count':len(offers)})
    for offer in offers:
        phone=(await db.execute(text('select phone_e164 from providers where id=:pid'),{'pid':offer['provider_id']})).scalar_one_or_none()
        if phone:
            await enqueue_channel(db,'whatsapp',phone.lstrip('+'),'text',{'body':f'New delivery job {job["id"]}. Reply ACCEPT {offer["id"]} to take it.'})
    customer_phone=(await db.execute(text('select u.phone_e164 from commerce_orders o join users u on u.id=o.user_id where o.id=:oid'),{'oid':order_id})).scalar_one_or_none()
    if customer_phone:
        await enqueue_channel(db,'whatsapp',customer_phone.lstrip('+'),'text',{'body':f'Delivery is being arranged for order {order_id}.'})
    return dict(job)

async def get_delivery(db: AsyncSession, job_id: UUID):
    row=(await db.execute(text('select * from delivery_jobs where id=:id'),{'id':job_id})).mappings().first()
    if not row: raise ValueError('delivery job not found')
    points=(await db.execute(text("""select st_y(location::geometry) lat,st_x(location::geometry) lng,heading,speed_kmh,recorded_at
      from delivery_tracking_points where delivery_job_id=:id order by recorded_at desc limit 20"""),{'id':job_id})).mappings().all()
    return {'job':dict(row),'tracking':[dict(p) for p in points]}

async def assign_courier(db: AsyncSession, job_id: UUID, courier_id: UUID):
    row=(await db.execute(text("""update delivery_jobs set courier_provider_id=:cid,status='assigned',assigned_at=now(),updated_at=now()
      where id=:jid and status='searching' returning *"""),{'cid':courier_id,'jid':job_id})).mappings().first()
    if not row: raise ValueError('delivery is no longer assignable')
    await db.execute(text("update service_requests set accepted_provider_id=:cid,status='accepted',version=version+1 where id=:rid and status in ('searching','offered')"),{'cid':courier_id,'rid':row['service_request_id']})
    await _event(db,job_id,'assigned','provider',courier_id,{'courier_id':str(courier_id)})
    return dict(row)

async def transition_delivery(db: AsyncSession, job_id: UUID, courier_id: UUID, new_status: str, reason: str|None=None):
    row=(await db.execute(text('select * from delivery_jobs where id=:jid for update'),{'jid':job_id})).mappings().first()
    if not row: raise ValueError('delivery job not found')
    if row['courier_provider_id'] != courier_id: raise ValueError('courier is not assigned')
    if new_status not in TRANSITIONS.get(row['status'],set()): raise ValueError(f"cannot transition {row['status']} to {new_status}")
    if new_status == 'delivered':
        proof=(await db.execute(text('select proof_type from delivery_proofs where delivery_job_id=:jid'),{'jid':job_id})).scalar_one_or_none()
        if not proof:
            raise ValueError('proof of delivery is required before marking delivered')
        await db.execute(text("update delivery_jobs set status='delivered',delivered_at=now(),updated_at=now() where id=:id"),{'id':job_id})
        await db.execute(text("update service_requests set status='completed',version=version+1 where id=:id and status in ('accepted','in_progress')"),{'id':row['service_request_id']})
    elif new_status == 'failed':
        await db.execute(text("update delivery_jobs set status='failed',failure_reason=:reason,failed_at=now(),updated_at=now() where id=:id"),{'id':job_id,'reason':reason or 'Delivery failed'})
    elif new_status == 'cancelled':
        await db.execute(text("update delivery_jobs set status='cancelled',failure_reason=:reason,cancelled_at=now(),updated_at=now() where id=:id"),{'id':job_id,'reason':reason or 'Delivery cancelled'})
        await db.execute(text("update service_requests set status='cancelled',version=version+1 where id=:id and status not in ('completed','cancelled')"),{'id':row['service_request_id']})
    elif new_status == 'picked_up':
        await db.execute(text("update delivery_jobs set status='picked_up',picked_up_at=now(),updated_at=now() where id=:id"),{'id':job_id})
        await db.execute(text("update service_requests set status='in_progress',version=version+1 where id=:id and status='accepted'"),{'id':row['service_request_id']})
    else:
        await db.execute(text('update delivery_jobs set status=:s,updated_at=now() where id=:id'),{'s':new_status,'id':job_id})
    await _event(db,job_id,new_status,'provider',courier_id,{'job_id':str(job_id),'status':new_status,'reason':reason} if reason else {'job_id':str(job_id),'status':new_status})
    phone=(await db.execute(text('select u.phone_e164 from delivery_jobs d join commerce_orders o on o.id=d.order_id join users u on u.id=o.user_id where d.id=:jid'),{'jid':job_id})).scalar_one_or_none()
    if phone:
        labels={'at_pickup':'Courier is at pickup.','picked_up':'Your order has been picked up.','in_transit':'Your order is on the way.','delivered':'Your order has been delivered.','failed':f'Delivery failed: {reason or "please contact support"}.','cancelled':'Delivery was cancelled.'}
        await enqueue_channel(db,'whatsapp',phone.lstrip('+'),'text',{'body':f'Delivery {job_id}: {labels[new_status]}'})
    return await get_delivery(db,job_id)

async def add_tracking_point(db: AsyncSession, job_id: UUID, courier_id: UUID, lat: float, lng: float, heading: float|None=None, speed_kmh: float|None=None):
    ownership=(await db.execute(text("select 1 from delivery_jobs where id=:jid and courier_provider_id=:cid and status in ('assigned','at_pickup','picked_up','in_transit')"),{'jid':job_id,'cid':courier_id})).first()
    if not ownership: raise ValueError('courier is not assigned to an active delivery')
    await db.execute(text("""insert into delivery_tracking_points(delivery_job_id,courier_provider_id,location,heading,speed_kmh)
      values(:jid,:cid,ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography,:heading,:speed)"""),{'jid':job_id,'cid':courier_id,'lat':lat,'lng':lng,'heading':heading,'speed':speed_kmh})
    await update_provider_location(db,courier_id,lat,lng,heading,speed_kmh)
    return {'job_id':job_id,'lat':lat,'lng':lng}

async def confirm_delivery_receipt(db: AsyncSession, job_id: UUID, user_id: UUID):
    ok=(await db.execute(text("""select d.id from delivery_jobs d join commerce_orders o on o.id=d.order_id
      where d.id=:jid and o.user_id=:uid and d.status='in_transit'"""), {'jid':job_id,'uid':user_id})).first()
    if not ok:
        raise ValueError('delivery is not available for customer confirmation')
    row=(await db.execute(text("""insert into delivery_proofs(delivery_job_id,proof_type,proof_hash,metadata)
      values(:jid,'recipient_confirmation',null,cast(:metadata as jsonb))
      on conflict(delivery_job_id) do update set proof_type=excluded.proof_type,metadata=excluded.metadata returning *"""),
      {'jid':job_id,'metadata':json.dumps({'confirmed_via':'whatsapp','actor':'customer'})})).mappings().one()
    await _event(db,job_id,'proof_recorded','customer',user_id,{'proof_type':'recipient_confirmation'})
    return dict(row)


async def add_proof(db: AsyncSession, job_id: UUID, courier_id: UUID, proof_type: str, proof_hash: str|None=None, metadata: dict|None=None):
    ok=(await db.execute(text("select 1 from delivery_jobs where id=:jid and courier_provider_id=:cid and status='in_transit'"),{'jid':job_id,'cid':courier_id})).first()
    if not ok: raise ValueError('delivery must be in transit')
    row=(await db.execute(text("""insert into delivery_proofs(delivery_job_id,proof_type,proof_hash,metadata)
      values(:jid,:ptype,:hash,cast(:metadata as jsonb)) on conflict(delivery_job_id) do update set proof_type=excluded.proof_type,proof_hash=excluded.proof_hash,metadata=excluded.metadata returning *"""),{'jid':job_id,'ptype':proof_type,'hash':proof_hash,'metadata':json.dumps(metadata or {})})).mappings().one()
    await _event(db,job_id,'proof_recorded','provider',courier_id,{'proof_type':proof_type})
    return dict(row)
