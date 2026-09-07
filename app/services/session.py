from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def get_or_create_session(db: AsyncSession, user_id: UUID, channel: str = 'whatsapp') -> UUID:
    row=(await db.execute(text("""select id from agent_sessions where user_id=:uid and channel=:channel and status='active' and expires_at>now() order by updated_at desc limit 1"""),{'uid':user_id,'channel':channel})).first()
    if row: return row[0]
    row=(await db.execute(text("""insert into agent_sessions(user_id,channel,state,expires_at) values(:uid,:channel,'{}'::jsonb,now()+interval '20 minutes') returning id"""),{'uid':user_id,'channel':channel})).one()
    return row[0]

async def save_session_state(db: AsyncSession, session_id: UUID, state: dict):
    import json
    await db.execute(text("""update agent_sessions set state=cast(:state as jsonb),updated_at=now(),expires_at=now()+interval '20 minutes' where id=:id and status='active'"""),{'id':session_id,'state':json.dumps(state)})
