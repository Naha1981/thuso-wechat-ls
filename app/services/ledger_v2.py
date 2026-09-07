import json
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def get_or_create_user_account(db: AsyncSession, user_id: UUID, currency: str='ZAR'):
    row=(await db.execute(text("""
      insert into ledger_accounts(owner_user_id,currency) values (:uid,:currency)
      on conflict do nothing
      returning id
    """), {'uid':user_id,'currency':currency})).scalar_one_or_none()
    if row: return row
    return (await db.execute(text('select id from ledger_accounts where owner_user_id=:uid and currency=:currency'), {'uid':user_id,'currency':currency})).scalar_one()

async def post_entry(db: AsyncSession, account_id: UUID, reference: str, direction: str, amount: Decimal, currency='ZAR', metadata=None):
    if amount <= 0: raise ValueError('amount must be positive')
    if direction not in ('credit','debit'): raise ValueError('invalid direction')
    await db.execute(text("""
      insert into wallet_ledger_entries(account_id,reference,direction,amount,currency,metadata)
      values (:account_id,:reference,:direction,:amount,:currency,cast(:metadata as jsonb))
      on conflict(account_id,reference,direction) do nothing
    """), {'account_id':account_id,'reference':reference,'direction':direction,'amount':amount,'currency':currency,'metadata':json.dumps(metadata or {})})

async def balance(db: AsyncSession, account_id: UUID):
    row=(await db.execute(text("""
      select coalesce(sum(case when direction='credit' then amount else -amount end),0) balance
      from wallet_ledger_entries where account_id=:id
    """), {'id':account_id})).scalar_one()
    return Decimal(str(row))

async def get_or_create_provider_account(db: AsyncSession, provider_id: UUID, currency: str='ZAR'):
    row=(await db.execute(text("""
      insert into ledger_accounts(owner_provider_id,currency) values (:pid,:currency)
      on conflict do nothing returning id
    """), {'pid':provider_id,'currency':currency})).scalar_one_or_none()
    if row: return row
    return (await db.execute(text('select id from ledger_accounts where owner_provider_id=:pid and currency=:currency'), {'pid':provider_id,'currency':currency})).scalar_one()
