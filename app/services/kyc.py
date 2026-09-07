from __future__ import annotations
from enum import StrEnum
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

class KYCError(Exception): pass
class KYCStatus(StrEnum): UNVERIFIED='unverified'; PENDING='pending'; VERIFIED='verified'; REJECTED='rejected'; EXPIRED='expired'

async def upsert_profile(db: AsyncSession, subject_id: UUID, subject_type: str, level: str='basic'):
    if subject_type not in ('customer','provider','business'): raise KYCError('invalid subject type')
    row=(await db.execute(text('''insert into kyc_profiles(subject_id,subject_type,level,status) values(:id,:type,:level,'pending')
      on conflict(subject_id,subject_type) do update set level=excluded.level, updated_at=now() returning *'''),{'id':subject_id,'type':subject_type,'level':level})).mappings().one()
    return dict(row)

async def set_status(db: AsyncSession, profile_id: UUID, status: str, reviewer_ref: str|None=None, reason: str|None=None):
    if status not in {s.value for s in KYCStatus}: raise KYCError('invalid KYC status')
    row=(await db.execute(text('''update kyc_profiles set status=:status, reviewer_ref=:reviewer, rejection_reason=:reason,
      verified_at=case when :status='verified' then now() else verified_at end, updated_at=now() where id=:id returning *'''),
      {'id':profile_id,'status':status,'reviewer':reviewer_ref,'reason':reason})).mappings().first()
    if not row: raise KYCError('KYC profile not found')
    return dict(row)
