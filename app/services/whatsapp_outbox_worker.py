from __future__ import annotations
import asyncio, json
from sqlalchemy import text
from app.core.db import SessionLocal
from app.services.outbox import claim_messages
from app.services.transport_registry import get_whatsapp_transport
from app.services.whatsapp_reliability import record_outbound_receipt, health_success, health_failure
from app.core.config import get_settings

async def deliver_once(limit: int = 25) -> int:
    async with SessionLocal() as db:
        rows = await claim_messages(db, limit); await db.commit()
    transport = get_whatsapp_transport()
    for row in rows:
        try:
            p = row['payload'] or {}; account = row.get('account_key') or p.get('account_key') or get_settings().whatsapp_operator_account_key
            if not account: raise RuntimeError('outbound WhatsApp account_key is required')
            if row['message_type']=='interactive':
                result=await transport.send_buttons(account,row['recipient'],p.get('body',''),[(b['id'],b['title']) for b in p.get('buttons',[])])
            elif row['message_type']=='location_request':
                result=await transport.request_location(account,row['recipient'],p.get('body','Please share your location.'))
            else:
                result=await transport.send_text(account,row['recipient'],p.get('body',''))
            provider_id=result.get('messageId') or result.get('provider_message_id') or (result.get('messages') or [{}])[0].get('id')
            async with SessionLocal() as db:
                await db.execute(text("update outbox_messages set status='sent',sent_at=now(),receipt_status='sent',provider_message_id=:pid where id=:id"),{'id':row['id'],'pid':provider_id})
                await record_outbound_receipt(db,outbox_message_id=row['id'],transport=transport.name,provider_message_id=provider_id,status='sent',metadata=result)
                await db.commit()
        except Exception as exc:
            async with SessionLocal() as db:
                await db.execute(text("update outbox_messages set status=case when attempts>=5 then 'failed' else 'pending' end,last_error=:err,available_at=now()+make_interval(secs=>least(300,power(2,attempts)::int*5)) where id=:id"),{'id':row['id'],'err':str(exc)[:1000]})
                await db.commit()
    return len(rows)

async def run_forever(interval: float=1.0):
    while True:
        await deliver_once(); await asyncio.sleep(interval)

if __name__=='__main__': asyncio.run(run_forever())
