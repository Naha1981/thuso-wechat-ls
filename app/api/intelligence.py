from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.identity import resolve_session
from app.services.media_intelligence import MediaError, create_intelligence_job, process_intelligence_job, claim_intelligence_jobs

router = APIRouter(prefix='/media-intelligence', tags=['media-intelligence'])

async def principal(authorization: str | None, db: AsyncSession) -> uuid.UUID:
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(401, 'authentication required')
    session = await resolve_session(db, authorization.split(' ', 1)[1].strip())
    if not session:
        raise HTTPException(401, 'invalid session')
    return session['user_id']

@router.post('/{media_id}/process')
async def process_media(media_id: uuid.UUID, authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    user_id = await principal(authorization, db)
    owner = (await db.execute(text('select owner_user_id from media_objects where id=:id'), {'id': media_id})).scalar_one_or_none()
    if owner != user_id:
        raise HTTPException(403, 'not authorized')
    try:
        result = await create_intelligence_job(db, media_id)
        await db.commit()
        return result
    except MediaError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc))

@router.get('/{media_id}')
async def get_media_intelligence(media_id: uuid.UUID, authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    user_id = await principal(authorization, db)
    rows = (await db.execute(text('''select r.* from media_intelligence_results r join media_objects m on m.id=r.media_id where r.media_id=:id and m.owner_user_id=:uid order by r.created_at desc'''), {'id': media_id, 'uid': user_id})).mappings().all()
    if not rows:
        raise HTTPException(404, 'no intelligence result')
    return {'results': [dict(r) for r in rows]}

@router.post('/worker/claim')
async def claim_worker(x_internal_secret: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    from app.core.config import get_settings
    if not x_internal_secret or x_internal_secret != get_settings().internal_webhook_secret:
        raise HTTPException(401, 'unauthorized')
    rows = await claim_intelligence_jobs(db)
    await db.commit()
    return {'jobs': rows}

@router.post('/worker/run/{job_id}')
async def run_worker(job_id: uuid.UUID, x_internal_secret: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    from app.core.config import get_settings
    if not x_internal_secret or x_internal_secret != get_settings().internal_webhook_secret:
        raise HTTPException(401, 'unauthorized')
    row = (await db.execute(text('select * from media_processing_jobs where id=:id'), {'id': job_id})).mappings().first()
    if not row:
        raise HTTPException(404, 'job not found')
    try:
        result = await process_intelligence_job(db, dict(row))
        await db.commit()
        return result
    except MediaError as exc:
        await db.commit()
        raise HTTPException(502, str(exc))
