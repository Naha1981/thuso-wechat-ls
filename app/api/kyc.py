from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.services.kyc import upsert_profile,set_status,KYCError
router=APIRouter(prefix='/kyc',tags=['kyc'])
class ProfileIn(BaseModel): subject_id:UUID; subject_type:str; level:str='basic'
class StatusIn(BaseModel): status:str; reviewer_ref:str|None=None; reason:str|None=None
@router.post('/profiles')
async def profile(body:ProfileIn,db:AsyncSession=Depends(get_db)):
    try: row=await upsert_profile(db,body.subject_id,body.subject_type,body.level); await db.commit(); return row
    except KYCError as e: await db.rollback(); raise HTTPException(409,str(e))
@router.post('/profiles/{profile_id}/status')
async def status(profile_id:UUID,body:StatusIn,db:AsyncSession=Depends(get_db)):
    try: row=await set_status(db,profile_id,body.status,body.reviewer_ref,body.reason); await db.commit(); return row
    except KYCError as e: await db.rollback(); raise HTTPException(409,str(e))
