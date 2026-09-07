from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.identity import normalize_phone, resolve_whatsapp_identity, create_session, revoke_session
from app.core.auth import require_session

router=APIRouter(prefix='/identity', tags=['identity'])
class BindIn(BaseModel):
    external_subject: str = Field(min_length=1,max_length=200)
    phone_e164: str
    display_name: str|None=None

@router.post('/whatsapp/bind')
async def bind_whatsapp(payload: BindIn, db: AsyncSession=Depends(get_db)):
    identity=await resolve_whatsapp_identity(db, external_subject=payload.external_subject, phone_e164=payload.phone_e164, display_name=payload.display_name)
    token,expires=await create_session(db, identity['user_id'], identity['id'])
    await db.commit()
    return {'user_id':str(identity['user_id']),'channel_identity_id':str(identity['id']),'token':token,'expires_at':expires}

@router.get('/me')
async def me(session=Depends(require_session), db: AsyncSession=Depends(get_db)):
    row=(await db.execute(__import__('sqlalchemy').text('select id,phone_e164,display_name,locale,created_at from users where id=:id'),{'id':session['user_id']})).mappings().one()
    roles=(await db.execute(__import__('sqlalchemy').text('select role,scope_type,scope_id from user_roles where user_id=:id order by role'),{'id':session['user_id']})).mappings().all()
    return {'user':dict(row),'roles':[dict(x) for x in roles]}

@router.post('/logout')
async def logout(authorization: str|None=__import__('fastapi').Header(default=None), db: AsyncSession=Depends(get_db)):
    if not authorization or not authorization.lower().startswith('bearer '): raise HTTPException(401,'Bearer session required')
    await revoke_session(db,authorization.split(' ',1)[1].strip()); await db.commit(); return {'ok':True}
