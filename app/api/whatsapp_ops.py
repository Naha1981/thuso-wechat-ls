from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import require_role
from app.core.db import get_db
from app.services.whatsapp_ops import overview, account_health, recent_failures, reset_circuit, transport_status

router=APIRouter(prefix='/ops/whatsapp', tags=['whatsapp-ops'])
Admin=Depends(require_role('admin'))

@router.get('/overview')
async def get_overview(_session=Admin, db: AsyncSession=Depends(get_db)):
    return await overview(db)

@router.get('/accounts')
async def get_accounts(_session=Admin, limit: int=Query(100, ge=1, le=1000), db: AsyncSession=Depends(get_db)):
    return {'accounts': await account_health(db, limit)}

@router.get('/transport')
async def get_transport_status(_session=Admin, db: AsyncSession=Depends(get_db)):
    return {'accounts': await transport_status(db)}

@router.get('/failures')
async def get_failures(_session=Admin, limit: int=Query(50, ge=1, le=500), db: AsyncSession=Depends(get_db)):
    return await recent_failures(db, limit)

@router.post('/accounts/{wa_account_id}/reset-circuit')
async def reset_account_circuit(wa_account_id: str, _session=Admin, db: AsyncSession=Depends(get_db)):
    if not await reset_circuit(db, wa_account_id):
        raise HTTPException(404, 'WhatsApp account health record not found')
    await db.commit()
    return {'ok': True, 'wa_account_id': wa_account_id, 'state': 'degraded'}
