from __future__ import annotations
import hashlib, hmac, secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings


def normalize_phone(value: str) -> str:
    raw = ''.join(ch for ch in value.strip() if ch.isdigit() or ch == '+')
    if raw.startswith('00'):
        raw = '+' + raw[2:]
    if not raw.startswith('+'):
        raise ValueError('phone must be E.164')
    digits = raw[1:]
    if not digits.isdigit() or not 8 <= len(digits) <= 15:
        raise ValueError('invalid E.164 phone')
    return '+' + digits


def hash_secret(value: str) -> str:
    pepper = get_settings().identity_pepper
    return hashlib.sha256((pepper + value).encode()).hexdigest()


def issue_session_token() -> str:
    return secrets.token_urlsafe(48)

async def resolve_whatsapp_identity(db: AsyncSession, *, external_subject: str, phone_e164: str, display_name: str | None = None) -> dict:
    phone = normalize_phone(phone_e164)
    row = (await db.execute(text("select id,user_id,phone_e164,status from channel_identities where channel='whatsapp' and external_subject=:subject"), {'subject': external_subject})).mappings().first()
    if row:
        await db.execute(text("update channel_identities set phone_e164=:phone, status='active', verified_at=coalesce(verified_at,now()), updated_at=now() where id=:id"), {'phone': phone, 'id': row['id']})
        return dict(row)
    user = (await db.execute(text("select id,phone_e164 from users where phone_e164=:phone"), {'phone': phone})).mappings().first()
    if not user:
        user = (await db.execute(text("insert into users(phone_e164,display_name) values(:phone,:name) returning id,phone_e164"), {'phone': phone, 'name': display_name})).mappings().one()
    identity = (await db.execute(text("insert into channel_identities(user_id,channel,external_subject,phone_e164,status,verified_at) values(:uid,'whatsapp',:subject,:phone,'active',now()) returning id,user_id,phone_e164,status"), {'uid': user['id'], 'subject': external_subject, 'phone': phone})).mappings().one()
    await db.execute(text("insert into identity_events(user_id,channel_identity_id,event_type,metadata) values(:uid,:iid,'whatsapp_identity_bound',jsonb_build_object('external_subject',:subject))"), {'uid': user['id'], 'iid': identity['id'], 'subject': external_subject})
    return dict(identity)

async def create_session(db: AsyncSession, user_id: UUID, channel_identity_id: UUID | None = None) -> tuple[str, datetime]:
    token = issue_session_token()
    expires = datetime.now(timezone.utc) + timedelta(minutes=get_settings().identity_session_ttl_minutes)
    await db.execute(text("insert into auth_sessions(user_id,channel_identity_id,token_hash,expires_at) values(:uid,:cid,:hash,:exp)"), {'uid': user_id, 'cid': channel_identity_id, 'hash': hash_secret(token), 'exp': expires})
    return token, expires

async def resolve_session(db: AsyncSession, token: str) -> dict | None:
    if not token: return None
    row = (await db.execute(text("select id,user_id,channel_identity_id,expires_at from auth_sessions where token_hash=:hash and revoked_at is null and expires_at>now()"), {'hash': hash_secret(token)})).mappings().first()
    if not row: return None
    await db.execute(text("update auth_sessions set last_seen_at=now() where id=:id"), {'id': row['id']})
    return dict(row)

async def revoke_session(db: AsyncSession, token: str) -> None:
    await db.execute(text("update auth_sessions set revoked_at=now() where token_hash=:hash and revoked_at is null"), {'hash': hash_secret(token)})

async def create_otp(db: AsyncSession, user_id: UUID, channel_identity_id: UUID, purpose: str) -> tuple[UUID, str, datetime]:
    code = f'{secrets.randbelow(1_000_000):06d}'
    expires = datetime.now(timezone.utc) + timedelta(seconds=get_settings().otp_ttl_seconds)
    challenge = (await db.execute(text("insert into otp_challenges(user_id,channel_identity_id,purpose,code_hash,expires_at,max_attempts) values(:uid,:cid,:purpose,:hash,:exp,:max) returning id,expires_at"), {'uid': user_id, 'cid': channel_identity_id, 'purpose': purpose, 'hash': hash_secret(code), 'exp': expires, 'max': get_settings().otp_max_attempts})).mappings().one()
    return challenge['id'], code, challenge['expires_at']

async def verify_otp(db: AsyncSession, challenge_id: UUID, code: str) -> bool:
    row = (await db.execute(text("select id,code_hash,attempts,max_attempts,expires_at,consumed_at from otp_challenges where id=:id for update"), {'id': challenge_id})).mappings().first()
    if not row or row['consumed_at'] or row['expires_at'] <= datetime.now(timezone.utc) or row['attempts'] >= row['max_attempts']:
        return False
    await db.execute(text("update otp_challenges set attempts=attempts+1 where id=:id"), {'id': challenge_id})
    if not hmac.compare_digest(row['code_hash'], hash_secret(code.strip())):
        return False
    await db.execute(text("update otp_challenges set consumed_at=now() where id=:id"), {'id': challenge_id})
    return True
