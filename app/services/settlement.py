from __future__ import annotations
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.financial import money, FinancialError

class SettlementError(Exception): pass

def split_settlement(gross: Decimal, platform_fee: Decimal):
    gross, platform_fee = money(gross), money(platform_fee)
    if gross <= 0 or platform_fee < 0 or platform_fee > gross:
        raise SettlementError('invalid settlement amounts')
    return gross, platform_fee, money(gross-platform_fee)

async def settle_payment(db: AsyncSession, payment_id: UUID, provider_id: UUID, platform_fee: Decimal|None=None):
    payment=(await db.execute(text('''select id,service_request_id,amount,currency,status from payments where id=:id for update'''),{'id':payment_id})).mappings().first()
    if not payment: raise SettlementError('payment not found')
    if payment['status'] != 'paid': raise SettlementError('payment is not captured')
    existing=(await db.execute(text('select * from payment_settlements where payment_id=:id for update'),{'id':payment_id})).mappings().first()
    if existing and existing['status']=='settled': return dict(existing)
    gross=money(payment['amount'])
    fee=money(platform_fee if platform_fee is not None else gross*Decimal('0.10'))
    gross,fee,provider_amount=split_settlement(gross,fee)
    ref=f'settlement:{payment_id}'
    journal=(await db.execute(text('''insert into financial_journals(journal_type,reference,currency,description)
      values('marketplace_settlement',:ref,:currency,:description)
      on conflict(reference) do update set reference=excluded.reference returning id'''),{'ref':ref,'currency':payment['currency'],'description':f'Settlement for payment {payment_id}'})).scalar_one()
    # Double-entry control accounts: PSP clearing -> platform revenue + provider payable.
    await db.execute(text('''insert into financial_journal_lines(journal_id,account_code,direction,amount,entity_type,entity_id)
      values(:jid,'payment_clearing','debit',:gross,'payment',:pid),
             (:jid,'platform_revenue','credit',:fee,'payment',:pid),
             (:jid,'provider_payable','credit',:earning,'provider',:provider_id)'''),
      {'jid':journal,'gross':gross,'fee':fee,'earning':provider_amount,'pid':payment_id,'provider_id':provider_id})
    row=(await db.execute(text('''insert into payment_settlements(payment_id,service_request_id,provider_id,currency,gross_amount,platform_fee,provider_amount,status,journal_id,settled_at)
      values(:pid,:rid,:provider,:currency,:gross,:fee,:earning,'settled',:jid,now())
      on conflict(payment_id) do update set status='settled',journal_id=excluded.journal_id,settled_at=coalesce(payment_settlements.settled_at,now())
      returning *'''),{'pid':payment_id,'rid':payment['service_request_id'],'provider':provider_id,'currency':payment['currency'],'gross':gross,'fee':fee,'earning':provider_amount,'jid':journal})).mappings().one()
    return dict(row)

async def hold_provider_reserve(db: AsyncSession, provider_id: UUID, payment_id: UUID, amount: Decimal, currency='LSL'):
    amount=money(amount)
    if amount<=0: raise SettlementError('reserve must be positive')
    ref=f'reserve:{payment_id}:{provider_id}'
    row=(await db.execute(text('''insert into provider_balance_reserves(provider_id,payment_id,amount,currency,status,reference)
      values(:pid,:payment,:amount,:currency,'held',:ref)
      on conflict(reference) do update set reference=excluded.reference returning *'''),{'pid':provider_id,'payment':payment_id,'amount':amount,'currency':currency,'ref':ref})).mappings().one()
    return dict(row)

async def release_reserve(db: AsyncSession, reserve_id: UUID):
    row=(await db.execute(text('''update provider_balance_reserves set status='released',released_at=now()
      where id=:id and status='held' returning *'''),{'id':reserve_id})).mappings().first()
    if not row: raise SettlementError('reserve unavailable')
    return dict(row)

async def payout_with_reservation(db: AsyncSession, payout_id: UUID):
    payout=(await db.execute(text('select * from provider_payouts where id=:id for update'),{'id':payout_id})).mappings().first()
    if not payout: raise SettlementError('payout not found')
    if payout['status'] not in ('requested','processing'): raise SettlementError('payout not executable')
    available=(await db.execute(text('''select coalesce(sum(case when direction='credit' then amount else -amount end),0)
      from wallet_ledger_entries le join ledger_accounts a on a.id=le.account_id
      where a.owner_provider_id=:pid and a.currency=:currency'''),{'pid':payout['provider_id'],'currency':payout['currency']})).scalar_one()
    reserved=(await db.execute(text('''select coalesce(sum(amount),0) from provider_balance_reserves where provider_id=:pid and currency=:currency and status='held' '''),{'pid':payout['provider_id'],'currency':payout['currency']})).scalar_one()
    if money(available)-money(reserved) < money(payout['amount']): raise SettlementError('insufficient available balance after reserves')
    attempt=(await db.execute(text('''insert into payout_attempts(payout_id,provider,channel,attempt_no,status)
      values(:id,'unconfigured','provider_payout','1','processing')
      on conflict(payout_id,attempt_no) do update set status='processing' returning *'''),{'id':payout_id})).mappings().one()
    return dict(attempt)
