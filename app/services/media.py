from __future__ import annotations

import hashlib
import mimetypes
import re
import secrets
import httpx
import os
import asyncio
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ALLOWED_MIME = {
    'image/jpeg', 'image/png', 'image/webp', 'image/gif',
    'video/mp4', 'video/3gpp', 'video/quicktime',
    'audio/ogg', 'audio/mpeg', 'audio/mp4', 'audio/aac', 'audio/wav',
    'application/pdf', 'application/zip', 'text/plain',
}
MAX_BYTES = {
    'image': 15 * 1024 * 1024,
    'video': 64 * 1024 * 1024,
    'audio': 32 * 1024 * 1024,
    'document': 32 * 1024 * 1024,
    'sticker': 2 * 1024 * 1024,
}

MAGIC = (
    (b'\xff\xd8\xff', 'image/jpeg'),
    (b'\x89PNG\r\n\x1a\n', 'image/png'),
    (b'RIFF', 'application/octet-stream'),
    (b'%PDF-', 'application/pdf'),
    (b'PK\x03\x04', 'application/zip'),
    (b'OggS', 'audio/ogg'),
    (b'ID3', 'audio/mpeg'),
)


def sanitize_filename(name: str | None) -> str | None:
    if not name:
        return None
    value = name.replace('\\', '_').replace('/', '_').replace('\x00', '')
    value = re.sub(r'[^A-Za-z0-9._ -]', '_', value).strip(' ._')
    return value[:180] or None


def sniff_mime(data: bytes, declared: str | None) -> str | None:
    for magic, mime in MAGIC:
        if data.startswith(magic):
            if magic == b'RIFF' and len(data) >= 12:
                if data[8:12] == b'WEBP':
                    return 'image/webp'
                if data[8:12] == b'WAVE':
                    return 'audio/wav'
            if mime == 'application/octet-stream':
                break
            return mime
    if declared in ALLOWED_MIME:
        # ISO-BMFF media (MP4/3GPP/M4A/QuickTime) carries an ftyp box at byte 4.
        if declared.startswith(('video/',)) or declared in {'audio/mp4'}:
            return declared if len(data) >= 12 and data[4:8] == b'ftyp' else None
        if declared == 'audio/wav':
            return declared if data.startswith(b'RIFF') and len(data) >= 12 and data[8:12] == b'WAVE' else None
        if declared == 'audio/ogg':
            return declared if data.startswith(b'OggS') else None
        if declared == 'audio/mpeg':
            return declared if data.startswith(b'ID3') or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0) else None
        if declared == 'application/pdf':
            return declared if data.startswith(b'%PDF-') else None
        if declared == 'application/zip':
            return declared if data.startswith(b'PK\x03\x04') else None
        if declared in {'image/jpeg','image/png','image/webp','image/gif'}:
            return None
        if declared == 'text/plain':
            return declared
    guessed, _ = mimetypes.guess_type('file.' + (declared or '').split('/')[-1])
    return declared if declared in ALLOWED_MIME and guessed else None


def content_key(sha256: str, mime: str | None) -> str:
    ext = mimetypes.guess_extension(mime or '') or '.bin'
    return f"sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}{ext}"


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class MediaError(ValueError):
    pass


async def register_inbound_media(
    db: AsyncSession,
    *,
    account_key: str,
    external_message_id: str,
    external_media_id: str | None,
    owner_user_id: UUID,
    media_type: str,
    mime_type: str | None,
    filename: str | None,
    metadata: dict | None = None,
) -> dict:
    if media_type not in MAX_BYTES:
        raise MediaError('unsupported media type')
    row = (await db.execute(text("""
        insert into media_objects(
          account_key,external_media_id,external_message_id,owner_user_id,media_type,
          mime_type,original_filename,metadata
        ) values(:account,:external_media,:message,:owner,:type,:mime,:filename,cast(:metadata as jsonb))
        on conflict(channel, account_key, external_message_id) where external_message_id is not null
        do update set owner_user_id=excluded.owner_user_id, mime_type=excluded.mime_type,
          original_filename=excluded.original_filename, metadata=excluded.metadata, updated_at=now()
        returning *
    """), {
        'account': account_key, 'external_media': external_media_id,
        'message': external_message_id, 'owner': owner_user_id, 'type': media_type,
        'mime': mime_type, 'filename': sanitize_filename(filename),
        'metadata': __import__('json').dumps(metadata or {}),
    })).mappings().one()
    return dict(row)


async def _scan_bytes(data: bytes) -> str:
    settings = __import__('app.core.config', fromlist=['get_settings']).get_settings()
    backend = settings.media_antivirus_backend.lower()
    if backend in {'none', 'disabled'}:
        return 'clean'
    if backend != 'clamav':
        return 'unavailable'
    try:
        reader, writer = await asyncio.open_connection(settings.clamav_host, settings.clamav_port)
        writer.write(b'zINSTREAM\0')
        for offset in range(0, len(data), 1024 * 1024):
            chunk = data[offset:offset + 1024 * 1024]
            writer.write(len(chunk).to_bytes(4, 'big'))
            writer.write(chunk)
        writer.write((0).to_bytes(4, 'big'))
        await writer.drain()
        response = await asyncio.wait_for(reader.read(4096), timeout=30)
        writer.close()
        if hasattr(writer, 'wait_closed'):
            await writer.wait_closed()
        text_response = response.decode(errors='replace').strip().lower()
        if text_response.endswith('ok'):
            return 'clean'
        if 'found' in text_response or 'infected' in text_response:
            return 'infected'
        return 'unavailable'
    except Exception:
        return 'unavailable'


async def _store_object(storage_key: str, data: bytes, mime_type: str) -> None:
    settings = __import__('app.core.config', fromlist=['get_settings']).get_settings()
    backend = settings.media_storage_backend.lower()
    if backend == 'local':
        root = Path(settings.media_local_root).resolve()
        target = (root / storage_key).resolve()
        if root not in target.parents:
            raise MediaError('invalid storage key')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return
    if backend != 'supabase':
        raise MediaError('unsupported media storage backend')
    url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{settings.media_bucket}/{storage_key}"
    headers = {
        'Authorization': f'Bearer {settings.supabase_service_role_key}',
        'apikey': settings.supabase_service_role_key,
        'Content-Type': mime_type,
        'x-upsert': 'true',
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, content=data, headers=headers)
    if response.status_code >= 300:
        raise MediaError(f'object storage upload failed: {response.status_code}')


async def store_media_bytes(
    db: AsyncSession,
    media_id: UUID,
    data: bytes,
    *,
    declared_mime: str | None,
    storage_key: str | None = None,
) -> dict:
    row = (await db.execute(text('select * from media_objects where id=:id for update'), {'id': media_id})).mappings().first()
    if not row:
        raise MediaError('media object not found')
    media_type = row['media_type']
    if len(data) > MAX_BYTES[media_type]:
        await db.execute(text("update media_objects set status='rejected',updated_at=now() where id=:id"), {'id': media_id})
        raise MediaError('media exceeds size limit')
    detected = sniff_mime(data, declared_mime)
    if not detected:
        await db.execute(text("update media_objects set status='rejected',scan_status='unavailable',updated_at=now() where id=:id"), {'id': media_id})
        raise MediaError('file type could not be validated')
    scan = await _scan_bytes(data)
    settings = __import__('app.core.config', fromlist=['get_settings']).get_settings()
    if scan == 'infected' or (scan == 'unavailable' and settings.media_antivirus_fail_closed):
        await db.execute(text("update media_objects set status='quarantined',scan_status=:scan,updated_at=now() where id=:id"), {'id': media_id, 'scan': scan})
        await db.execute(text("insert into media_events(media_id,event_type,actor_type,payload) values(:id,'quarantined','system',cast(:payload as jsonb))"), {'id': media_id, 'payload': __import__('json').dumps({'scan_status': scan})})
        raise MediaError('media failed security scanning')
    digest = hash_bytes(data)
    final_key = content_key(digest, detected)
    await _store_object(final_key, data, detected)
    await db.execute(text("""
        update media_objects set size_bytes=:size,sha256=:sha,detected_mime_type=:detected,
          storage_key=:key,status='ready',scan_status=:scan_status,updated_at=now()
        where id=:id
    """), {'id': media_id, 'size': len(data), 'sha': digest, 'detected': detected, 'key': final_key, 'scan_status': scan})
    await db.execute(text("""
        insert into media_events(media_id,event_type,actor_type,payload)
        values(:id,'ready','system',cast(:payload as jsonb))
    """), {'id': media_id, 'payload': __import__('json').dumps({'size_bytes': len(data), 'sha256': digest, 'mime': detected})})
    return {'id': media_id, 'storage_key': final_key, 'sha256': digest, 'mime_type': detected, 'size_bytes': len(data)}


async def create_access_grant(db: AsyncSession, media_id: UUID, audience_user_id: UUID | None, ttl_seconds: int = 300) -> tuple[str, dict]:
    if ttl_seconds < 1 or ttl_seconds > 3600:
        raise MediaError('ttl must be between 1 and 3600 seconds')
    row = (await db.execute(text("select id,status,owner_user_id,storage_key from media_objects where id=:id"), {'id': media_id})).mappings().first()
    if not row or row['status'] != 'ready':
        raise MediaError('media is not available')
    raw = secrets.token_urlsafe(32)
    grant = (await db.execute(text("""
      insert into media_access_grants(media_id,audience_user_id,scope,token_hash,expires_at)
      values(:media,:audience,'read',:hash,now() + (:ttl * interval '1 second'))
      returning id,expires_at
    """), {'media': media_id, 'audience': audience_user_id, 'hash': token_hash(raw), 'ttl': ttl_seconds})).mappings().one()
    return raw, {'id': grant['id'], 'media_id': media_id, 'expires_at': grant['expires_at'], 'storage_key': row['storage_key']}


async def authorize_grant(db: AsyncSession, media_id: UUID, raw_token: str) -> dict | None:
    row = (await db.execute(text("""
      select g.*,m.storage_key,m.detected_mime_type,m.size_bytes
      from media_access_grants g join media_objects m on m.id=g.media_id
      where g.media_id=:media and g.token_hash=:hash and g.revoked_at is null and g.expires_at>now() and m.status='ready'
      limit 1
    """), {'media': media_id, 'hash': token_hash(raw_token)})).mappings().first()
    return dict(row) if row else None
