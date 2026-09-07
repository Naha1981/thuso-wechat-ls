from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.auth import require_session
from app.core.principal import require_courier_access, require_request_access, require_role
from app.services.delivery import get_delivery, assign_courier, transition_delivery, add_tracking_point, add_proof

router=APIRouter(prefix='/delivery',tags=['delivery'])

class TrackIn(BaseModel):
    lat: float=Field(ge=-90,le=90); lng: float=Field(ge=-180,le=180)
    heading: float|None=None; speed_kmh: float|None=Field(default=None,ge=0)
class ProofIn(BaseModel):
    proof_type: str; proof_hash: str|None=None; metadata: dict={}
class FailIn(BaseModel): reason: str=Field(min_length=1,max_length=500)

@router.get('/jobs/{job_id}')
async def detail(job_id: UUID, db: AsyncSession=Depends(get_db), session=Depends(require_session)):
    job=await get_delivery(db,job_id)
    if not job: raise HTTPException(404,'delivery job not found')
    try:
        await require_courier_access(db, job_id, session)
        return job
    except HTTPException as courier_denied:
        if courier_denied.status_code != 403: raise
        req_id=job.get('service_request_id')
        if req_id: await require_request_access(db, UUID(str(req_id)), session); return job
        raise

@router.post('/jobs/{job_id}/assign/{courier_id}')
async def assign(job_id: UUID,courier_id: UUID,db: AsyncSession=Depends(get_db), session=Depends(require_session)):
    await require_role(db, session, {'admin','dispatcher','merchant_manager'})
    try:r=await assign_courier(db,job_id,courier_id)
    except ValueError as e:raise HTTPException(409,str(e))
    await db.commit();return r

@router.post('/jobs/{job_id}/status/{status}')
async def status(job_id: UUID,status: str,db: AsyncSession=Depends(get_db), session=Depends(require_session)):
    courier=await require_courier_access(db, job_id, session)
    if status not in {'at_pickup','picked_up','in_transit','delivered','failed','cancelled'}:raise HTTPException(422,'invalid delivery status')
    try:r=await transition_delivery(db,job_id,UUID(str(courier['courier_provider_id'])),status)
    except ValueError as e:raise HTTPException(409,str(e))
    await db.commit();return r

@router.post('/jobs/{job_id}/fail')
async def fail(job_id: UUID,body: FailIn,db: AsyncSession=Depends(get_db), session=Depends(require_session)):
    courier=await require_courier_access(db, job_id, session)
    try:r=await transition_delivery(db,job_id,UUID(str(courier['courier_provider_id'])),'failed',body.reason)
    except ValueError as e:raise HTTPException(409,str(e))
    await db.commit();return r

@router.post('/jobs/{job_id}/tracking')
async def tracking(job_id: UUID,body: TrackIn,db: AsyncSession=Depends(get_db), session=Depends(require_session)):
    courier=await require_courier_access(db, job_id, session)
    try:r=await add_tracking_point(db,job_id,UUID(str(courier['courier_provider_id'])),body.lat,body.lng,body.heading,body.speed_kmh)
    except ValueError as e:raise HTTPException(409,str(e))
    await db.commit();return r

@router.post('/jobs/{job_id}/proof')
async def proof(job_id: UUID,body: ProofIn,db: AsyncSession=Depends(get_db), session=Depends(require_session)):
    courier=await require_courier_access(db, job_id, session)
    if body.proof_type not in {'otp','photo','signature','recipient_confirmation'}:raise HTTPException(422,'invalid proof type')
    try:r=await add_proof(db,job_id,UUID(str(courier['courier_provider_id'])),body.proof_type,body.proof_hash,body.metadata)
    except ValueError as e:raise HTTPException(409,str(e))
    await db.commit();return r
