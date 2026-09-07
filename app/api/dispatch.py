from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.auth import require_session
from app.core.principal import require_provider_access, require_request_access, require_role
from app.services.dispatch import dispatch_wave, reassign_if_needed, update_provider_location, expire_offers

router=APIRouter(prefix='/dispatch',tags=['dispatch'])
class LocationIn(BaseModel):
 lat: float=Field(ge=-90,le=90); lng: float=Field(ge=-180,le=180); heading: float|None=None; speed_kmh: float|None=Field(default=None,ge=0)

@router.post('/requests/{request_id}/run')
async def run(request_id:UUID,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await require_role(db,session,{'admin','dispatcher'})
 row=(await db.execute(text('select category,pickup_lat,pickup_lng,status from service_requests where id=:id'),{'id':request_id})).mappings().first()
 if not row: raise HTTPException(404,'request not found')
 if row['status'] not in {'searching','offered'}: raise HTTPException(409,f"request is {row['status']}")
 offers=await dispatch_wave(db,request_id,row['category'],row['pickup_lat'],row['pickup_lng']); await db.commit(); return {'request_id':request_id,'offers':offers}

@router.post('/requests/{request_id}/reassign')
async def reassign(request_id:UUID,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await require_role(db,session,{'admin','dispatcher'})
 row=(await db.execute(text('select category,pickup_lat,pickup_lng from service_requests where id=:id'),{'id':request_id})).mappings().first()
 if not row: raise HTTPException(404,'request not found')
 offers=await reassign_if_needed(db,request_id,row['category'],row['pickup_lat'],row['pickup_lng']); await db.commit(); return {'request_id':request_id,'offers':offers}

@router.post('/offers/expire')
async def expire(db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await require_role(db,session,{'admin','dispatcher'})
 count=await expire_offers(db); await db.commit(); return {'expired':count}

@router.put('/providers/{provider_id}/location')
async def location(provider_id:UUID,body:LocationIn,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 await require_provider_access(db,provider_id,session)
 try: await update_provider_location(db,provider_id,body.lat,body.lng,body.heading,body.speed_kmh)
 except ValueError as e: raise HTTPException(422,str(e))
 await db.commit(); return {'provider_id':provider_id,'updated':True}
