from __future__ import annotations

import asyncio
import json
import uuid
from sqlalchemy import text
from app.core.db import SessionLocal
from app.services.whatsapp_reliability import claim_inbox_events, mark_inbox_processed, mark_inbox_failed, recover_stale_inbox_events
from app.services.whatsapp_router import handle_whatsapp_message
from app.services.outbox import enqueue_channel
from app.core.identity import resolve_whatsapp_identity


def _outbound_payload(out):
    if out.actions:
        return {
            'body': out.reply,
            'buttons': [
                {'id': f'agent:confirm:{out.actions[0].id}', 'title': 'Confirm'},
                {'id': f'agent:decline:{out.actions[0].id}', 'title': 'Decline'},
            ],
        }
    return {'body': out.reply}


async def process_inbox_event(row: dict) -> None:
    payload = row['payload'] or {}
    wa = payload.get('message') or payload.get('whatsapp_message') or {}
    if not wa:
        raise ValueError('inbox event has no message payload')

    account_key = row.get('account_key') or str(payload.get('account_id') or 'meta')
    phone = str(wa.get('from_e164') or wa.get('from') or '')
    if not phone:
        raise ValueError('WhatsApp message has no sender phone')
    phone_e164 = phone if phone.startswith('+') else '+' + phone
    external_subject = str(payload.get('account_id') or payload.get('account_jid') or account_key)
    message_id = str(wa.get('id') or row['external_event_id'])
    wa['from'] = phone_e164.lstrip('+')
    wa['id'] = message_id

    async with SessionLocal() as db:
        identity = await resolve_whatsapp_identity(
            db,
            external_subject=external_subject,
            phone_e164=phone_e164,
            display_name=wa.get('push_name'),
        )
        if account_key and account_key != 'meta':
            await db.execute(text("update channel_identities set wa_account_id=(select id from wa_accounts where account_key=:key) where id=:id"), {'key': account_key, 'id': identity['id']})
        dedup = await db.execute(text("""
            insert into agent_message_dedup(channel,external_message_id)
            values('whatsapp',:id)
            on conflict(channel,external_message_id) do nothing returning id
        """), {'id': message_id})
        if not dedup.first():
            await db.commit()
            return

        await db.execute(text("""
            insert into conversation_messages(
              user_id,channel,direction,external_message_id,message_type,body,metadata
            ) values(
              :uid,'whatsapp','inbound',:eid,:type,:body,cast(:meta as jsonb)
            ) on conflict(channel,external_message_id) do nothing
        """), {
            'uid': identity['user_id'],
            'eid': message_id,
            'type': wa.get('type', 'text'),
            'body': wa.get('body'),
            'meta': json.dumps(payload),
        })

        out = await handle_whatsapp_message(
            db,
            user_id=identity['user_id'],
            phone_e164=phone_e164,
            message=wa,
        )
        await enqueue_channel(
            db,
            'whatsapp',
            wa['from'],
            'interactive' if out.actions else ('location_request' if out.request_location else 'text'),
            _outbound_payload(out), account_key=account_key if account_key != 'meta' else None,
            trace_id=str(row.get('trace_id')) if row.get('trace_id') else None,
        )
        await db.commit()


async def drain_once(limit: int = 25) -> int:
    async with SessionLocal() as db:
        await recover_stale_inbox_events(db)
        rows = await claim_inbox_events(db, limit)
        await db.commit()
    processed = 0
    for row in rows:
        try:
            await process_inbox_event(row)
            async with SessionLocal() as db:
                await mark_inbox_processed(db, row['id'])
                await db.commit()
            processed += 1
        except Exception as exc:
            async with SessionLocal() as db:
                await mark_inbox_failed(db, row['id'], str(exc))
                await db.commit()
    return processed


async def run_forever(interval: float = 0.5):
    while True:
        await drain_once()
        await asyncio.sleep(interval)


if __name__ == '__main__':
    asyncio.run(run_forever())
