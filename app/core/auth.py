from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.identity import resolve_session

async def require_session(authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(401, 'Bearer session required')
    token = authorization.split(' ', 1)[1].strip()
    session = await resolve_session(db, token)
    if not session:
        raise HTTPException(401, 'Invalid or expired session')
    session['_token'] = token
    return session

async def require_role(role: str, session=Depends(require_session), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    row = (await db.execute(text("select 1 from user_roles where user_id=:uid and role=:role limit 1"), {'uid': session['user_id'], 'role': role})).first()
    if not row:
        raise HTTPException(403, 'Required role not granted')
    return session
