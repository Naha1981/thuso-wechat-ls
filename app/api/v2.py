from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.auth import require_session
from app.core.principal import require_merchant_access
from app.models import Provider, ServiceRequest, POSProduct
from app.schemas.domain import *
from app.services.dispatch import find_nearby_providers
from app.services.pos import create_order

router=APIRouter(prefix='/platform',tags=['platform'])

@router.post('/providers',status_code=201)
async def onboard_provider(body:ProviderCreateV2,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 owner=session['user_id']
 p=Provider(owner_user_id=owner,category=body.category,business_name=body.business_name,status='pending',metadata={**body.metadata,'phone_e164':body.phone_e164})
 db.add(p); await db.flush()
 if body.lat is not None and body.lng is not None:
  await db.execute(text("UPDATE providers SET location=ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography WHERE id=:id"),{'lng':body.lng,'lat':body.lat,'id':p.id})
 await db.commit(); await db.refresh(p); return {'id':p.id,'status':p.status}

@router.post('/requests',response_model=ServiceRequestOutV2,status_code=201)
async def request_service(body:ServiceRequestCreateV2,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 req=ServiceRequest(user_id=session['user_id'],category=body.category,status='searching',pickup_lat=body.pickup_lat,pickup_lng=body.pickup_lng,payload={**body.payload,'description':body.description,'destination_lat':body.destination_lat,'destination_lng':body.destination_lng})
 db.add(req); await db.commit(); await db.refresh(req)
 if body.pickup_lat is not None and body.pickup_lng is not None: req.payload['matches']=await find_nearby_providers(db,body.category,body.pickup_lat,body.pickup_lng)
 return req

@router.get('/providers/nearby')
async def nearby(category:str,lat:float,lng:float,db:AsyncSession=Depends(get_db)): return await find_nearby_providers(db,category,lat,lng)

@router.post('/pos/products',status_code=201)
async def create_product(merchant_id,body:POSProductCreate,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await require_merchant_access(db,merchant_id,session)
 p=POSProduct(merchant_id=merchant_id,name=body.name,sku=body.sku,price=body.price,stock_quantity=body.stock_quantity); db.add(p); await db.commit(); await db.refresh(p); return {'id':p.id,'sku':p.sku}

@router.post('/pos/orders',status_code=201)
async def create_pos_order(body:POSOrderCreate,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await require_merchant_access(db,body.merchant_id,session)
 try: order=await create_order(db,body.merchant_id,body.items)
 except ValueError as e: raise HTTPException(400,str(e))
 await db.commit(); return {'id':order.id,'total':str(order.total),'status':order.status}

@router.post('/career/cv')
async def generate_cv(body:CVRequest,session=Depends(require_session)):
 return {'user_id':str(session['user_id']),'target_role':body.target_role,'profile':body.profile,'status':'queued','next':'connect an LLM provider/agent worker'}
@router.post('/education/tutor')
async def tutor(body:TutorRequest,session=Depends(require_session)):
 return {'user_id':str(session['user_id']),'grade':body.grade,'subject':body.subject,'topic':body.topic,'status':'queued'}
@router.post('/mental-health/session')
async def mental_health(session=Depends(require_session)):
 return {'user_id':str(session['user_id']),'status':'created','safety':'This service is supportive, not emergency care or diagnosis.'}
