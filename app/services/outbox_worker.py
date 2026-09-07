from __future__ import annotations
import asyncio, json
from app.core.db import SessionLocal
from app.services.outbox import claim_messages
from app.services.transport_registry import get_whatsapp_transport

async def deliver_once(limit:int=25)->int:
    async with SessionLocal() as db:
        rows=await claim_messages(db,limit)
        await db.commit()
    if not rows: return 0
    transport=get_whatsapp_transport()
    for row in rows:
        try:
            p=row['payload'] or {}
            if row['message_type']=='interactive':
                result=await transport.send_buttons(p.get('account_key') or __import__('app.core.config', fromlist=['get_settings']).get_settings().whatsapp_operator_account_key, row['recipient'],p['body'],[(b['id'],b['title']) for b in p.get('buttons',[])])
            elif row['message_type']=='location_request':
                result=await transport.request_location(p.get('account_key') or __import__('app.core.config', fromlist=['get_settings']).get_settings().whatsapp_operator_account_key, row['recipient'],p.get('body','Please share your location.'))
            else:
                result=await transport.send_text(p.get('account_key') or __import__('app.core.config', fromlist=['get_settings']).get_settings().whatsapp_operator_account_key, row['recipient'],p.get('body',''))
            async with SessionLocal() as db:
                await db.execute(__import__('sqlalchemy').text("update outbox_messages set status='sent',sent_at=now() where id=:id"),{'id':row['id']})
                await db.execute(__import__('sqlalchemy').text("insert into conversation_messages(user_id,channel,direction,external_message_id,message_type,body,metadata) select u.id,'whatsapp','outbound',:eid,:type,:body,cast(:meta as jsonb) from users u where u.phone_e164=:phone"),{'eid':(result.get('messages') or [{}])[0].get('id'),'type':row['message_type'],'body':p.get('body'),'meta':json.dumps(result),'phone':'+'+row['recipient'] if not row['recipient'].startswith('+') else row['recipient']})
                await db.commit()
        except Exception as exc:
            async with SessionLocal() as db:
                await db.execute(__import__('sqlalchemy').text("update outbox_messages set status=case when attempts>=5 then 'failed' else 'pending' end,last_error=:err,available_at=now()+make_interval(secs=>least(300,power(2,attempts)::int*5)) where id=:id"),{'id':row['id'],'err':str(exc)[:1000]})
                await db.commit()
    return len(rows)

async def run_forever(interval:float=1.0):
    while True:
        await deliver_once(); await asyncio.sleep(interval)

if __name__=='__main__': asyncio.run(run_forever())
