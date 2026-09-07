from __future__ import annotations
import json
from fastapi import APIRouter, Request, Response
from sqlalchemy import text, select
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import verify_meta_signature
from app.models import User
from app.core.identity import resolve_whatsapp_identity
from app.services.payments import settle_verified_payment


router=APIRouter()

@router.get('/whatsapp')
async def verify_whatsapp(request: Request):
    q=request.query_params; s=get_settings()
    if q.get('hub.verify_token') != s.whatsapp_verify_token: return Response(status_code=403)
    return Response(q.get('hub.challenge',''),media_type='text/plain')

@router.post('/whatsapp')
async def receive_whatsapp(request: Request):
    s=get_settings(); raw=await request.body()
    if len(raw)>s.webhook_max_body_bytes: return Response(status_code=413)
    verify_meta_signature(raw,request.headers.get('x-hub-signature-256'),s.whatsapp_app_secret)
    try: payload=json.loads(raw)
    except json.JSONDecodeError: return Response(status_code=400)
    wa=_extract_message(payload)
    if not wa: return {'ok':True}
    from app.services.whatsapp_reliability import record_inbox_event
    async with SessionLocal() as db:
        event_id, created = await record_inbox_event(
            db, transport='meta', account_key='meta',
            external_event_id=wa['id'], event_type='message',
            payload={'event':'message','account_id':'meta','message':wa},
        )
        await db.commit()
    return {'ok':True,'accepted':True,'duplicate':not created,'event_id':str(event_id)}

def _outbound_payload(out):
    if out.actions:
        return {'body':out.reply,'buttons':[{'id':f"agent:confirm:{out.actions[0].id}",'title':'Confirm'},{'id':f"agent:decline:{out.actions[0].id}",'title':'Decline'}]}
    if out.request_location: return {'body':out.reply}
    return {'body':out.reply}

def _extract_message(payload: dict) -> dict | None:
    try:
        for entry in payload.get('entry',[]):
            for change in entry.get('changes',[]):
                for msg in change.get('value',{}).get('messages',[]):
                    result={'id':msg['id'],'from':msg['from'],'type':msg['type']}
                    if msg.get('type')=='text': result['body']=msg.get('text',{}).get('body','')
                    elif msg.get('type')=='location':
                        loc=msg.get('location',{}); result.update({'body':'location','latitude':loc.get('latitude'),'longitude':loc.get('longitude')})
                    elif msg.get('type')=='interactive':
                        i=msg.get('interactive',{}); rep=i.get('button_reply') or i.get('list_reply') or {}; result['body']=rep.get('id','')
                    return result
    except (KeyError,TypeError): return None
    return None


@router.post('/whatsapp/baileys/receipt')
async def receive_baileys_receipt(request: Request):
    import hmac, hashlib
    s=get_settings(); raw=await request.body()
    if len(raw)>s.webhook_max_body_bytes: return Response(status_code=413)
    supplied=request.headers.get('x-webhook-signature',''); expected=hmac.new(s.webhook_secret.encode(),raw,hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(expected,supplied): return Response(status_code=401)
    try: payload=json.loads(raw)
    except json.JSONDecodeError: return Response(status_code=400)
    receipt=payload.get('receipt') or {}; message_id=str(receipt.get('message_id') or '')
    if not message_id: return Response(status_code=400)
    from app.services.whatsapp_reliability import record_outbound_receipt
    async with SessionLocal() as db:
        row=(await db.execute(text("select id from outbox_messages where provider_message_id=:mid order by created_at desc limit 1"),{'mid':message_id})).first()
        if row:
            await record_outbound_receipt(db,outbox_message_id=row[0],transport='baileys',provider_message_id=message_id,status=str(receipt.get('status') or 'unknown'),metadata=receipt)
        await db.commit()
    return {'ok':True,'matched':bool(row)}

@router.post('/payments/{provider}')
async def payment_webhook(provider: str, request: Request):
    from app.core.payment_security import verify_hmac
    s=get_settings(); raw=await request.body()
    signature=request.headers.get('x-payment-signature')
    if not verify_hmac(raw,signature,s.payment_webhook_secret): return Response(status_code=401)
    try: payload=json.loads(raw)
    except json.JSONDecodeError: return Response(status_code=400)
    external_id=str(payload.get('id') or payload.get('event_id') or '')
    payment_id=payload.get('payment_id')
    if not external_id or not payment_id: return Response(status_code=400)
    async with SessionLocal() as db:
        row=await db.execute(text("insert into payment_webhook_events(provider,external_id,signature_valid,payload) values(:p,:e,true,cast(:payload as jsonb)) on conflict(provider,external_id) do nothing returning id"),{'p':provider,'e':external_id,'payload':raw.decode()})
        if not row.first(): return {'ok':True,'duplicate':True}
        result=await settle_verified_payment(db,__import__('uuid').UUID(str(payment_id)),str(payload.get('provider_reference') or external_id))
        await db.execute(text("update payment_webhook_events set processed_at=now() where provider=:p and external_id=:e"),{'p':provider,'e':external_id})
        await db.commit()
    return {'ok':True,'payment':result}

@router.post('/whatsapp/baileys')
async def receive_baileys_webhook(request: Request):
    """Durable ingress: authenticate, persist, and ACK; domain work is asynchronous."""
    import hmac, hashlib
    s=get_settings(); raw=await request.body()
    if len(raw)>s.webhook_max_body_bytes: return Response(status_code=413)
    supplied=request.headers.get('x-webhook-signature','')
    expected=hmac.new(s.webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(expected,supplied): return Response(status_code=401)
    try: payload=json.loads(raw)
    except json.JSONDecodeError: return Response(status_code=400)
    if payload.get('event') != 'message': return {'ok':True,'ignored':True}
    wa=payload.get('message') or {}
    account_key=str(payload.get('account_id') or payload.get('account_jid') or '')
    phone=str(wa.get('from_e164') or wa.get('from') or '')
    if not phone: return Response(status_code=400)
    wa['from']=phone.lstrip('+')
    wa['id']=wa.get('id') or str(__import__('uuid').uuid4())
    from app.services.whatsapp_reliability import record_inbox_event
    async with SessionLocal() as db:
        event_id, created = await record_inbox_event(
            db, transport='baileys', account_key=account_key,
            external_event_id=str(wa['id']), event_type='message', payload=payload,
        )
        # Media registration is intentionally kept at ingress so the operator can
        # upload bytes after receiving the media_ids in this ACK response.
        media_ids=[]
        if created and wa.get('type') in ('image','video','audio','document','sticker'):
            identity=await resolve_whatsapp_identity(
                db, external_subject=account_key, phone_e164=phone, display_name=wa.get('push_name')
            )
            from app.services.media import register_inbound_media
            media=await register_inbound_media(
                db, account_key=account_key, external_message_id=wa['id'],
                external_media_id=wa.get('media_id'), owner_user_id=identity['user_id'],
                media_type=wa['type'], mime_type=wa.get('mime_type'),
                filename=wa.get('filename'), metadata=wa.get('media_metadata') or {},
            )
            media_ids.append(str(media['id']))
            if wa['type']=='audio':
                await db.execute(text("insert into voice_transcriptions(media_id) values(:id) on conflict(media_id) do nothing"), {'id':media['id']})
                await db.execute(text("insert into media_processing_jobs(media_id,job_type) values(:id,'transcribe') on conflict(media_id,job_type) do nothing"), {'id':media['id']})
        await db.commit()
    return {'ok':True,'accepted':True,'duplicate':not created,'event_id':str(event_id),'media_ids':media_ids}
