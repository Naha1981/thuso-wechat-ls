from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.core.principal import require_user_access

PAIRING_PURPOSE = 'platform'

async def create_pairing_session(db: AsyncSession, *, session: dict, label: str | None = None) -> dict:
    user_id = uuid.UUID(str(session['user_id']))
    await require_user_access(db, user_id, session)
    account_key = f"wa-{uuid.uuid4().hex}"
    row = (await db.execute(text("""
        insert into wa_accounts(account_key, owner_user_id, label, purpose, status)
        values(:key,:uid,:label,:purpose,'stopped')
        returning id,account_key,status
    """), {'key': account_key, 'uid': user_id, 'label': label, 'purpose': PAIRING_PURPOSE})).mappings().one()
    expires = datetime.now(timezone.utc) + timedelta(seconds=300)
    onboarding = (await db.execute(text("""
        insert into whatsapp_onboarding_sessions(user_id,wa_account_id,status,expires_at)
        values(:uid,:aid,'starting',:exp)
        returning id,status,expires_at
    """), {'uid': user_id, 'aid': row['id'], 'exp': expires})).mappings().one()
    await db.execute(text("""
        insert into whatsapp_identity_events(user_id,wa_account_id,event_type,metadata)
        values(:uid,:aid,'pairing_started',jsonb_build_object('purpose',:purpose))
    """), {'uid': user_id, 'aid': row['id'], 'purpose': PAIRING_PURPOSE})
    return {**dict(row), 'onboarding_id': onboarding['id'], 'expires_at': onboarding['expires_at']}

async def get_pairing_status(db: AsyncSession, *, session: dict, onboarding_id: uuid.UUID) -> dict:
    uid = uuid.UUID(str(session['user_id']))
    row = (await db.execute(text("""
      select o.id onboarding_id,o.status onboarding_status,o.expires_at,
             a.id account_id,a.account_key,a.status,a.connection_state,a.phone_e164,
             a.qr_code,a.qr_created_at,a.last_connected_at,a.last_disconnect_code,a.last_disconnect_message,a.paired_at
      from whatsapp_onboarding_sessions o join wa_accounts a on a.id=o.wa_account_id
      where o.id=:oid and o.user_id=:uid
    """), {'oid': onboarding_id, 'uid': uid})).mappings().first()
    if not row:
        return None
    d = dict(row)
    now = datetime.now(timezone.utc)
    if d['onboarding_status'] not in ('completed','cancelled') and d['expires_at'] <= now:
        await db.execute(text("update whatsapp_onboarding_sessions set status='expired',cancelled_at=coalesce(cancelled_at,now()) where id=:id and completed_at is null and cancelled_at is null"), {'id': onboarding_id})
        d['onboarding_status'] = 'expired'
    if d['status'] == 'connected' and d['onboarding_status'] != 'completed':
        await db.execute(text("update whatsapp_onboarding_sessions set status='completed',completed_at=now() where id=:id and completed_at is null"), {'id': onboarding_id})
        await db.execute(text("update wa_accounts set paired_at=coalesce(paired_at,now()) where id=:id"), {'id': d['account_id']})
        await db.execute(text("insert into whatsapp_identity_events(user_id,wa_account_id,event_type) values(:uid,:aid,'pairing_completed')"), {'uid': uid, 'aid': d['account_id']})
        d['onboarding_status'] = 'completed'
    return d

async def cancel_pairing(db: AsyncSession, *, session: dict, onboarding_id: uuid.UUID) -> None:
    uid = uuid.UUID(str(session['user_id']))
    row = (await db.execute(text("select wa_account_id from whatsapp_onboarding_sessions where id=:id and user_id=:uid for update"), {'id': onboarding_id, 'uid': uid})).mappings().first()
    if not row:
        raise ValueError('pairing session not found')
    await db.execute(text("update whatsapp_onboarding_sessions set status='cancelled',cancelled_at=now() where id=:id and completed_at is null and cancelled_at is null"), {'id': onboarding_id})
    await db.execute(text("update wa_accounts set revoked_at=now(),status='stopped',qr_code=null where id=:id"), {'id': row['wa_account_id']})
    await db.execute(text("insert into whatsapp_identity_events(user_id,wa_account_id,event_type) values(:uid,:aid,'pairing_cancelled')"), {'uid': uid, 'aid': row['wa_account_id']})
