from __future__ import annotations
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def require_user_access(db: AsyncSession, user_id: UUID, session: dict) -> dict:
    if UUID(str(session['user_id'])) != UUID(str(user_id)):
        raise HTTPException(403, 'user access denied')
    row = (await db.execute(text("select id,phone_e164,display_name,locale from users where id=:id"), {'id': user_id})).mappings().first()
    if not row:
        raise HTTPException(404, 'user not found')
    return dict(row)

async def require_provider_access(db: AsyncSession, provider_id: UUID, session: dict) -> dict:
    row = (await db.execute(text("select id, owner_user_id, category, status, business_name from providers where id=:id"), {'id': provider_id})).mappings().first()
    if not row: raise HTTPException(404, 'provider not found')
    owner = UUID(str(row['owner_user_id']))
    uid = UUID(str(session['user_id']))
    role = (await db.execute(text("select 1 from user_roles where user_id=:uid and role='admin' limit 1"), {'uid': uid})).first()
    scoped = (await db.execute(text("select 1 from user_roles where user_id=:uid and role in ('provider','provider_manager') and scope_type='provider' and scope_id=:pid limit 1"), {'uid': uid, 'pid': provider_id})).first()
    if owner != uid and not role and not scoped:
        raise HTTPException(403, 'provider access denied')
    return dict(row)

async def require_merchant_access(db: AsyncSession, merchant_id: UUID, session: dict) -> dict:
    row = (await db.execute(text("select id, owner_user_id, category, status, business_name from providers where id=:id"), {'id': merchant_id})).mappings().first()
    if not row: raise HTTPException(404, 'merchant not found')
    if row['category'] not in ('restaurant','merchant','retail'):
        raise HTTPException(403, 'merchant access denied')
    uid = UUID(str(session['user_id']))
    role = (await db.execute(text("select 1 from user_roles where user_id=:uid and role='admin' limit 1"), {'uid': uid})).first()
    scoped = (await db.execute(text("select 1 from user_roles where user_id=:uid and role in ('merchant','merchant_manager') and scope_type='merchant' and scope_id=:mid limit 1"), {'uid': uid, 'mid': merchant_id})).first()
    if UUID(str(row['owner_user_id'])) != uid and not role and not scoped:
        raise HTTPException(403, 'merchant access denied')
    return dict(row)

async def require_request_access(db: AsyncSession, request_id: UUID, session: dict) -> dict:
    row = (await db.execute(text("select id,user_id,accepted_provider_id,category,status from service_requests where id=:id"), {'id': request_id})).mappings().first()
    if not row: raise HTTPException(404, 'request not found')
    uid = UUID(str(session['user_id']))
    if UUID(str(row['user_id'])) == uid:
        return dict(row)
    if row['accepted_provider_id']:
        p = await require_provider_access(db, UUID(str(row['accepted_provider_id'])), session)
        if p: return dict(row)
    admin = (await db.execute(text("select 1 from user_roles where user_id=:uid and role='admin' limit 1"), {'uid': uid})).first()
    if admin: return dict(row)
    raise HTTPException(403, 'request access denied')

async def require_courier_access(db: AsyncSession, job_id: UUID, session: dict) -> dict:
    row = (await db.execute(text("""select d.id,d.service_request_id,d.courier_provider_id,d.status,p.owner_user_id,p.category
        from delivery_jobs d join providers p on p.id=d.courier_provider_id where d.id=:id"""), {'id': job_id})).mappings().first()
    if not row: raise HTTPException(404, 'delivery job not found')
    uid = UUID(str(session['user_id']))
    scoped = (await db.execute(text("select 1 from user_roles where user_id=:uid and role in ('courier','courier_manager') and scope_type='provider' and scope_id=:pid limit 1"), {'uid': uid, 'pid': row['courier_provider_id']})).first()
    admin = (await db.execute(text("select 1 from user_roles where user_id=:uid and role='admin' limit 1"), {'uid': uid})).first()
    if row['category'] != 'delivery' or (UUID(str(row['owner_user_id'])) != uid and not scoped and not admin):
        raise HTTPException(403, 'courier access denied')
    return dict(row)

async def require_role(db: AsyncSession, session: dict, roles: set[str]) -> dict:
    if not roles:
        raise HTTPException(403, 'no roles configured')
    rows = (await db.execute(text("select role,scope_type,scope_id from user_roles where user_id=:uid and role = any(:roles)"), {'uid': session['user_id'], 'roles': list(roles)})).mappings().all()
    if not rows:
        raise HTTPException(403, 'required role not granted')
    return {'roles': [dict(r) for r in rows]}
