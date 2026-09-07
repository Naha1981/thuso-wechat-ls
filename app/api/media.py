from __future__ import annotations

import hashlib
import hmac
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
import httpx
from app.core.config import get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.identity import resolve_session, resolve_whatsapp_identity
from app.services.media import MediaError, authorize_grant, create_access_grant, register_inbound_media, store_media_bytes

router = APIRouter(tags=['media'])
settings = get_settings()


def _internal_signature(body: bytes, signature: str | None) -> None:
    if not settings.webhook_secret or not signature:
        raise HTTPException(401, 'invalid media webhook')
    expected = hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, 'invalid media webhook')


async def _principal(authorization: str | None, db: AsyncSession) -> UUID:
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(401, 'authentication required')
    session = await resolve_session(db, authorization.split(' ', 1)[1].strip())
    if not session:
        raise HTTPException(401, 'invalid session')
    return session['user_id']


@router.post('/media/inbound')
async def inbound_media(
    request: Request,
    x_webhook_signature: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()
    _internal_signature(body, x_webhook_signature)
    try:
        payload = json.loads(body)
        identity = await resolve_whatsapp_identity(db, external_subject=str(payload['account_key']), phone_e164=str(payload['phone_e164']))
        media = await register_inbound_media(db, account_key=str(payload['account_key']), external_message_id=str(payload['message_id']),
            external_media_id=payload.get('media_id'), owner_user_id=identity['user_id'], media_type=str(payload['media_type']),
            mime_type=payload.get('mime_type'), filename=payload.get('filename'), metadata=payload.get('metadata') or {})
        await db.commit()
        return {'ok': True, 'media': media}
    except (KeyError, ValueError, MediaError) as exc:
        await db.rollback()
        raise HTTPException(400, str(exc))


@router.post('/media/inbound-bytes/{media_id}')
async def inbound_bytes(
    media_id: UUID,
    request: Request,
    x_webhook_signature: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()
    _internal_signature(body, x_webhook_signature)
    declared = request.headers.get('x-media-mime')
    try:
        row = (await db.execute(text('select storage_key from media_objects where id=:id'), {'id': media_id})).mappings().first()
        if not row:
            raise MediaError('media object not found')
        result = await store_media_bytes(db, media_id, body, declared_mime=declared)
        await db.commit()
        return {'ok': True, **result}
    except MediaError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc))


@router.get('/media/{media_id}/content')
async def media_content(media_id: UUID, token: str, db: AsyncSession = Depends(get_db)):
    grant = await authorize_grant(db, media_id, token)
    if not grant:
        raise HTTPException(404, 'media not found or grant expired')
    s = get_settings()
    if s.media_storage_backend.lower() == 'local':
        root = __import__('pathlib').Path(s.media_local_root).resolve()
        target = (root / grant['storage_key']).resolve()
        if root not in target.parents or not target.exists():
            raise HTTPException(404, 'media object missing')
        return FileResponse(target, media_type=grant.get('detected_mime_type') or 'application/octet-stream')
    url = f"{s.supabase_url.rstrip('/')}/storage/v1/object/sign/{s.media_bucket}/{grant['storage_key']}"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, headers={'Authorization': f'Bearer {s.supabase_service_role_key}', 'apikey': s.supabase_service_role_key}, json={'expiresIn': max(1, int((grant['expires_at'] - __import__('datetime').datetime.now(__import__('datetime').timezone.utc)).total_seconds()))})
    if response.status_code >= 300:
        raise HTTPException(502, 'storage signing failed')
    signed = response.json().get('signedURL') or response.json().get('signedUrl')
    if not signed:
        raise HTTPException(502, 'storage did not return a signed URL')
    if signed.startswith('/'):
        signed = s.supabase_url.rstrip('/') + '/storage/v1' + signed
    return RedirectResponse(signed, status_code=307)


@router.post('/media/{media_id}/grant')
async def grant_media(media_id: UUID, request: Request, authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    user_id = await _principal(authorization, db)
    owner = (await db.execute(text('select owner_user_id from media_objects where id=:id'), {'id': media_id})).scalar_one_or_none()
    if owner != user_id:
        raise HTTPException(403, 'not authorized')
    payload = await request.json()
    try:
        token, grant = await create_access_grant(db, media_id, user_id, int(payload.get('ttl_seconds', 300)))
        await db.commit()
        return {'token': token, 'content_url': f'/api/v1/media/{media_id}/content?token={token}', **grant}
    except MediaError as exc:
        await db.rollback()
        raise HTTPException(400, str(exc))
