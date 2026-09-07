from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.models import User, Provider, ServiceRequest
from app.schemas.api import UserCreate, UserOut, ProviderCreate, ServiceRequestCreate, ServiceRequestOut

router = APIRouter()

@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.phone_e164 == body.phone_e164))
    if existing: return existing
    user = User(phone_e164=body.phone_e164, display_name=body.display_name)
    db.add(user); await db.commit(); await db.refresh(user)
    return user

@router.post("/providers", status_code=201)
async def create_provider(body: ProviderCreate, db: AsyncSession = Depends(get_db)):
    provider = Provider(**body.model_dump())
    db.add(provider); await db.commit(); await db.refresh(provider)
    return {"id": provider.id, "status": provider.status}

@router.post("/service-requests", response_model=ServiceRequestOut, status_code=201)
async def create_service_request(body: ServiceRequestCreate, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, body.user_id)
    if not user: raise HTTPException(404, "User not found")
    req = ServiceRequest(**body.model_dump())
    db.add(req); await db.commit(); await db.refresh(req)
    return req

@router.get("/service-requests/{request_id}", response_model=ServiceRequestOut)
async def get_service_request(request_id: str, db: AsyncSession = Depends(get_db)):
    req = await db.get(ServiceRequest, request_id)
    if not req: raise HTTPException(404, "Service request not found")
    return req
