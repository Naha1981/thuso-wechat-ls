from __future__ import annotations
import json
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.config import get_settings
from app.services.realtime import acquire_dispatch_lease, release_dispatch_lease

router = APIRouter(prefix='/realtime', tags=['realtime'])

async def require_internal(x_internal_secret: str|None=Header(default=None)):
    secret = get_settings().internal_webhook_secret
    if not secret or x_internal_secret != secret:
        raise HTTPException(401, 'internal realtime endpoint requires authenticated worker')

@router.post('/requests/{request_id}/lease')
async def acquire_lease(request_id: UUID, db: AsyncSession=Depends(get_db), _: None=Depends(require_internal)):
    import socket, os
    owner=f'{socket.gethostname()}:{os.getpid()}'
    ok=await acquire_dispatch_lease(db, request_id, owner)
    await db.commit()
    return {'request_id':str(request_id),'acquired':ok,'owner':owner}

@router.delete('/requests/{request_id}/lease')
async def release_lease(request_id: UUID, db: AsyncSession=Depends(get_db), _: None=Depends(require_internal)):
    import socket, os
    owner=f'{socket.gethostname()}:{os.getpid()}'
    await release_dispatch_lease(db, request_id, owner)
    await db.commit()
    return {'request_id':str(request_id),'released':True}

@router.get('/requests/{request_id}/events')
async def request_events(request_id: UUID, after_id: str='0-0', _: None=Depends(require_internal)):
    redis=Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        rows=await redis.xrange('naha:marketplace:events', min=after_id, max='+', count=200)
        events=[]
        for sid, fields in rows:
            if fields.get('aggregate_id') == str(request_id):
                try: payload=json.loads(fields.get('payload','{}'))
                except json.JSONDecodeError: payload={}
                events.append({'stream_id':sid,'event_id':fields.get('event_id'),'event_type':fields.get('event_type'),'payload':payload})
        return {'request_id':str(request_id),'events':events}
    finally:
        await redis.aclose()
