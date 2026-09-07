from __future__ import annotations
import json, uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.agent.commands import parse
from app.agent.core import classify, IntentName, Intent
from app.agent.responses import response_for
from app.services.agent_execution import create_action, approve_and_execute, AgentExecutionError
from app.services.session import get_or_create_session, save_session_state
from app.services.memory import record_turn, recent_context, refresh_summary

router=APIRouter(prefix='/agent', tags=['agent'])

class AgentMessageIn(BaseModel):
    user_id: uuid.UUID
    text: str = Field(min_length=1, max_length=4000)
    channel: str = Field(default='whatsapp', max_length=30)
    external_message_id: str | None = Field(default=None, max_length=200)
    latitude: float | None = None
    longitude: float | None = None

class AgentAction(BaseModel):
    id: uuid.UUID | None = None
    action: str
    requires_confirmation: bool
    payload: dict = Field(default_factory=dict)

class AgentMessageOut(BaseModel):
    reply: str
    intent: str
    confidence: float
    actions: list[AgentAction] = Field(default_factory=list)
    trace_id: uuid.UUID
    request_location: bool = False

class ConfirmIn(BaseModel):
    user_id: uuid.UUID
    action_id: uuid.UUID
    approved: bool

async def process_message(body: AgentMessageIn, db: AsyncSession) -> AgentMessageOut:
    trace_id=uuid.uuid4()
    await record_turn(db, user_id=body.user_id, channel=body.channel, text_value=body.text)
    context = await recent_context(db, user_id=body.user_id, channel=body.channel)
    intent=classify(body.text)
    parsed=parse(body.text)
    if parsed:
        mapped={'ride':IntentName.RIDE,'mechanic':IntentName.MECHANIC,'handyman':IntentName.HANDYMAN,'cv':IntentName.CAREER,'cancel':IntentName.CANCEL,'status':IntentName.STATUS,'help':IntentName.HELP}
        if parsed.command in mapped: intent=Intent(mapped[parsed.command],1.0,parsed.args)
    session_id=await get_or_create_session(db, body.user_id, body.channel)
    actions=[]; request_location=False
    service_intents={IntentName.RIDE,IntentName.MECHANIC,IntentName.HANDYMAN,IntentName.FOOD}
    if body.latitude is not None and body.longitude is not None:
        session=(await db.execute(text("select state from agent_sessions where id=:id for update"),{'id':session_id})).mappings().first()
        state=(session or {}).get('state') or {}
        pending=state.get('pending_service')
        if pending:
            intent=Intent(IntentName(pending['category']),1.0,pending.get('args',{}))
            intent.args['pickup_lat']=body.latitude; intent.args['pickup_lng']=body.longitude
            payload={'category':intent.name.value,**intent.args}
            key=f"{body.channel}:{body.external_message_id or trace_id}:create_service_request"
            saved=await create_action(db,user_id=body.user_id,session_id=session_id,action='create_service_request',payload=payload,risk='medium',idempotency_key=key)
            await save_session_state(db,session_id,{})
            actions=[AgentAction(id=saved['id'],action='create_service_request',requires_confirmation=True,payload=payload)]
            return AgentMessageOut(reply=f"📍 Location received. Please confirm the request:\n\n{intent.name.value.title()}\nLocation: {body.latitude:.5f}, {body.longitude:.5f}\n\nTap Confirm to continue.",intent=intent.name.value,confidence=1.0,actions=actions,trace_id=trace_id)
    if not intent.args.get('crisis_signal') and intent.name in service_intents:
        if body.latitude is None or body.longitude is None:
            await save_session_state(db,session_id,{'pending_service':{'category':intent.name.value,'args':intent.args}})
            request_location=True
        else:
            intent.args['pickup_lat']=body.latitude; intent.args['pickup_lng']=body.longitude
    if not intent.args.get('crisis_signal') and intent.name in {IntentName.CANCEL}:
        action='cancel_request'; payload={'request_id':intent.args.get('request_id')} ; risk='high'
        if payload['request_id']:
            key=f"{body.channel}:{body.external_message_id or trace_id}:{action}"
            saved=await create_action(db,user_id=body.user_id,session_id=session_id,action=action,payload=payload,risk=risk,idempotency_key=key)
            actions=[AgentAction(id=saved['id'],action=action,requires_confirmation=True,payload=payload)]
    elif not intent.args.get('crisis_signal') and intent.name in service_intents and not request_location:
        payload={'category':intent.name.value,**intent.args}; key=f"{body.channel}:{body.external_message_id or trace_id}:create_service_request"
        saved=await create_action(db,user_id=body.user_id,session_id=session_id,action='create_service_request',payload=payload,risk='medium',idempotency_key=key)
        actions=[AgentAction(id=saved['id'],action='create_service_request',requires_confirmation=True,payload=payload)]
    reply=response_for(intent.name,crisis=bool(intent.args.get('crisis_signal')))
    # Context is currently exposed through the service boundary for downstream
    # model/routing adapters; deterministic intent behavior remains unchanged.
    _ = context
    await refresh_summary(db, user_id=body.user_id, channel=body.channel)
    return AgentMessageOut(reply=reply,intent=intent.name.value,confidence=intent.confidence,actions=actions,trace_id=trace_id,request_location=request_location)

@router.post('/messages', response_model=AgentMessageOut)
async def message(body: AgentMessageIn, db: AsyncSession=Depends(get_db)):
    out=await process_message(body,db); await db.commit(); return out

@router.post('/confirm')
async def confirm(body: ConfirmIn, db: AsyncSession=Depends(get_db)):
    if not body.approved:
        row=await db.execute(text("update agent_actions set status='declined' where id=:id and user_id=:uid and status='pending' returning id"),{'id':body.action_id,'uid':body.user_id})
        if not row.first(): raise HTTPException(404,'pending action not found')
        await db.execute(text("insert into agent_action_events(action_id,event_type,actor_user_id,payload) values(:id,'declined',:uid,'{}'::jsonb)"),{'id':body.action_id,'uid':body.user_id})
        await db.commit(); return {'status':'declined','action_id':body.action_id}
    try:
        result=await approve_and_execute(db,action_id=body.action_id,user_id=body.user_id); await db.commit()
        return {'status':'executed','action_id':body.action_id,'result':result}
    except AgentExecutionError as e:
        await db.rollback(); raise HTTPException(409,str(e))
