from __future__ import annotations
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.financial import money, FinancialError

class ReconciliationError(Exception): pass

async def create_batch(db: AsyncSession, provider: str, currency: str, period_start, period_end):
    if period_end <= period_start: raise ReconciliationError('invalid reconciliation period')
    row=(await db.execute(text('''insert into reconciliation_batches(provider,currency,period_start,period_end)
      values(:provider,:currency,:start,:end) returning *'''),{'provider':provider,'currency':currency,'start':period_start,'end':period_end})).mappings().one()
    return dict(row)

async def match_item(db: AsyncSession, batch_id: UUID, external_reference: str, amount: Decimal, currency: str, external_status: str='paid', metadata=None):
    amount=money(amount)
    payment=(await db.execute(text('''select id,amount,currency,status from payments
      where provider_reference=:ref or reference=:ref limit 1'''),{'ref':external_reference})).mappings().first()
    if payment and money(payment['amount']) == amount and payment['currency'] == currency and payment['status'] in ('paid','refunded'):
        item=(await db.execute(text('''insert into reconciliation_items(batch_id,external_reference,payment_id,amount,currency,external_status,internal_status,match_status,metadata)
          values(:batch,:ref,:pid,:amount,:currency,:external,:internal,'matched',cast(:metadata as jsonb))
          on conflict(batch_id,external_reference) do update set match_status='matched',payment_id=excluded.payment_id,internal_status=excluded.internal_status,metadata=excluded.metadata
          returning *'''),{'batch':batch_id,'ref':external_reference,'pid':payment['id'],'amount':amount,'currency':currency,'external':external_status,'internal':payment['status'],'metadata':__import__('json').dumps(metadata or {})})).mappings().one()
        return dict(item)
    code='NOT_FOUND' if not payment else ('AMOUNT_MISMATCH' if money(payment['amount']) != amount else 'STATE_OR_CURRENCY_MISMATCH')
    item=(await db.execute(text('''insert into reconciliation_items(batch_id,external_reference,amount,currency,external_status,internal_status,match_status,mismatch_code,metadata)
      values(:batch,:ref,:amount,:currency,:external,:internal,'exception',:code,cast(:metadata as jsonb))
      on conflict(batch_id,external_reference) do update set match_status='exception',mismatch_code=excluded.mismatch_code,metadata=excluded.metadata
      returning *'''),{'batch':batch_id,'ref':external_reference,'amount':amount,'currency':currency,'external':external_status,'internal':payment['status'] if payment else None,'code':code,'metadata':__import__('json').dumps(metadata or {})})).mappings().one()
    await db.execute(text('''insert into reconciliation_exceptions(batch_id,item_id,code,severity,description)
      values(:batch,:item,:code,'high',:description)'''),{'batch':batch_id,'item':item['id'],'code':code,'description':f'Reconciliation exception {code} for {external_reference}'})
    return dict(item)

async def close_batch(db: AsyncSession, batch_id: UUID):
    counts=(await db.execute(text('''select count(*) filter(where match_status='matched') matched,
      count(*) filter(where match_status='exception') exceptions from reconciliation_items where batch_id=:id'''),{'id':batch_id})).mappings().one()
    status='exception' if counts['exceptions'] else 'matched'
    row=(await db.execute(text('''update reconciliation_batches set status=:status,matched_count=:matched,exception_count=:exceptions,closed_at=now()
      where id=:id and status='open' returning *'''),{'id':batch_id,'status':status,'matched':counts['matched'],'exceptions':counts['exceptions']})).mappings().first()
    if not row: raise ReconciliationError('batch unavailable or already closed')
    return dict(row)

async def verify_destination(db: AsyncSession, provider_id: UUID, rail: str, destination_ref: str, currency='LSL'):
    if not destination_ref.strip(): raise ReconciliationError('destination reference required')
    row=(await db.execute(text('''insert into payout_destinations(provider_id,rail,destination_ref,currency,status,verified_at)
      values(:pid,:rail,:dest,:currency,'verified',now())
      on conflict(provider_id,rail,destination_ref) do update set status='verified',verified_at=now()
      returning *'''),{'pid':provider_id,'rail':rail,'dest':destination_ref,'currency':currency})).mappings().one()
    return dict(row)

async def execute_payout(db: AsyncSession, payout_id: UUID, rail: str, destination_ref: str):
    payout=(await db.execute(text('select * from provider_payouts where id=:id for update'),{'id':payout_id})).mappings().first()
    if not payout: raise ReconciliationError('payout not found')
    if payout['status'] not in ('requested','processing'): raise ReconciliationError('payout not executable')
    destination=(await db.execute(text('''select * from payout_destinations where provider_id=:pid and rail=:rail and destination_ref=:dest and status='verified' '''),{'pid':payout['provider_id'],'rail':rail,'dest':destination_ref})).mappings().first()
    if not destination: raise ReconciliationError('payout destination is not verified')
    attempt=(await db.execute(text('''insert into payout_attempts(payout_id,provider,channel,attempt_no,status)
      select :id,:provider,:rail,coalesce(max(attempt_no),0)+1,'processing' from payout_attempts where payout_id=:id
      returning *'''),{'id':payout_id,'provider':destination['rail'],'rail':rail})).mappings().one()
    await db.execute(text("update provider_payouts set status='processing' where id=:id"),{'id':payout_id})
    return dict(attempt)

async def complete_payout(db: AsyncSession, attempt_id: UUID, external_reference: str):
    row=(await db.execute(text('''update payout_attempts set status='succeeded',external_reference=:ref,completed_at=now()
      where id=:id and status='processing' returning *'''),{'id':attempt_id,'ref':external_reference})).mappings().first()
    if not row: raise ReconciliationError('payout attempt unavailable')
    payout=(await db.execute(text('''update provider_payouts set status='paid',paid_at=now()
      where id=:id and status='processing' returning *'''),{'id':row['payout_id']})).mappings().first()
    if not payout: raise ReconciliationError('payout state transition failed')
    return {'attempt':dict(row),'payout':dict(payout)}
