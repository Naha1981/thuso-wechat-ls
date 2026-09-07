from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.auth import require_session
from app.core.principal import require_provider_access, require_request_access, require_role
from app.services.execution import create_offers, accept_offer, transition_request
from app.services.outbox import enqueue
from app.services.payments import create_payment

router=APIRouter(prefix='/execution',tags=['execution'])
@router.post('/requests/{request_id}/dispatch')
async def dispatch(request_id:UUID,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await require_role(db,session,{'admin','dispatcher'})
 req=(await db.execute(text('select id,category,pickup_lat,pickup_lng,status from service_requests where id=:id'),{'id':request_id})).mappings().first()
 if not req: raise HTTPException(404,'request not found')
 if req['status'] not in ('searching','offered'): raise HTTPException(409,'request cannot be dispatched')
 offers=await create_offers(db,request_id,req['category'],req['pickup_lat'],req['pickup_lng']); await enqueue(db,'service_request',request_id,'service.offers_created',{'offer_count':len(offers)}); await db.commit(); return {'request_id':request_id,'offers_created':len(offers),'offers':offers}

@router.post('/offers/{offer_id}/accept')
async def accept(offer_id:UUID,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 row=(await db.execute(text('select provider_id,service_request_id from service_offers where id=:id'),{'id':offer_id})).mappings().first()
 if not row: raise HTTPException(404,'offer not found')
 await require_provider_access(db,UUID(str(row['provider_id'])),session)
 try: request_id=await accept_offer(db,offer_id,UUID(str(row['provider_id'])))
 except ValueError as e: raise HTTPException(409,str(e))
 await enqueue(db,'service_request',request_id,'service.accepted',{'provider_id':str(row['provider_id']),'offer_id':str(offer_id)}); await db.commit(); return {'request_id':request_id,'provider_id':row['provider_id'],'status':'accepted'}

@router.post('/requests/{request_id}/transition')
async def transition(request_id:UUID,status:str=Query(...,pattern='^(in_progress|completed|cancelled)$'),db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 req=await require_request_access(db,request_id,session)
 if status=='cancelled' and UUID(str(req['user_id']))==UUID(str(session['user_id'])):
  pass
 elif req['accepted_provider_id']:
  await require_provider_access(db,UUID(str(req['accepted_provider_id'])),session)
 else: raise HTTPException(403,'request transition denied')
 try: await transition_request(db,request_id,status)
 except ValueError as e: raise HTTPException(409,str(e))
 await enqueue(db,'service_request',request_id,f'service.{status}',{}); await db.commit(); return {'request_id':request_id,'status':status}

@router.post('/payments')
async def payment(amount:Decimal=Query(...,gt=0),reference:str=Query(...,min_length=3,max_length=120),service_request_id:UUID|None=None,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 if service_request_id: await require_request_access(db,service_request_id,session)
 row=await create_payment(db,session['user_id'],amount,reference,service_request_id); await db.commit(); return row

@router.get('/requests/{request_id}')
async def request_status(request_id:UUID,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await require_request_access(db,request_id,session)
 row=(await db.execute(text("select id,user_id,category,status,pickup_lat,pickup_lng,accepted_provider_id,created_at,completed_at,cancelled_at from service_requests where id=:id"),{'id':request_id})).mappings().first()
 if not row: raise HTTPException(404,'request not found')
 offers=(await db.execute(text("select id,provider_id,status,quoted_amount,eta_seconds,expires_at,responded_at from service_offers where service_request_id=:id order by created_at"),{'id':request_id})).mappings().all()
 return {'request':dict(row),'offers':[dict(x) for x in offers]}

@router.post('/providers/{provider_id}/location')
async def provider_location(provider_id:UUID,latitude:float=Query(...,ge=-90,le=90),longitude:float=Query(...,ge=-180,le=180),db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await require_provider_access(db,provider_id,session)
 await db.execute(text("insert into provider_locations(provider_id,location,updated_at) values(:pid,ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography,now()) on conflict(provider_id) do update set location=excluded.location,updated_at=now()"),{'pid':provider_id,'lat':latitude,'lng':longitude}); await db.commit(); return {'provider_id':provider_id,'latitude':latitude,'longitude':longitude}
