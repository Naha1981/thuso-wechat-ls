from __future__ import annotations
from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings

class AccountRoutingError(RuntimeError):
    pass

@dataclass(frozen=True)
class OutboundAccount:
    account_key: str
    account_id: str
    transport: str

async def resolve_outbound_account(db: AsyncSession, *, recipient: str, explicit_account_key: str | None = None) -> OutboundAccount:
    """Resolve a WhatsApp sending account without silently choosing the wrong tenant.

    Priority: explicit account -> identity's bound account -> sole active account -> fail closed.
    """
    if explicit_account_key:
        row = (await db.execute(text("""
            select id,account_key,transport from wa_accounts
            where account_key=:key and revoked_at is null and status <> 'stopped'
            limit 1
        """), {'key': explicit_account_key})).mappings().first()
        if not row:
            raise AccountRoutingError('explicit WhatsApp account is not active or does not exist')
        return OutboundAccount(str(row['account_key']), str(row['id']), str(row['transport']))

    phone = recipient if recipient.startswith('+') else '+' + recipient
    rows = (await db.execute(text("""
        select distinct a.id,a.account_key,a.transport
        from channel_identities ci
        join wa_accounts a on a.id=ci.wa_account_id
        where ci.channel='whatsapp' and ci.phone_e164=:phone
          and ci.status='active' and a.revoked_at is null and a.status <> 'stopped'
        order by a.created_at desc
    """), {'phone': phone})).mappings().all()
    if len(rows) == 1:
        r = rows[0]; return OutboundAccount(str(r['account_key']), str(r['id']), str(r['transport']))
    if len(rows) > 1:
        raise AccountRoutingError('multiple active WhatsApp accounts match recipient; account_key is required')

    active = (await db.execute(text("""
        select id,account_key,transport from wa_accounts
        where revoked_at is null and status <> 'stopped'
        order by created_at desc limit 2
    """))).mappings().all()
    if len(active) == 1:
        r=active[0]; return OutboundAccount(str(r['account_key']), str(r['id']), str(r['transport']))

    default_key = get_settings().whatsapp_operator_account_key
    if default_key and len(active) == 0:
        row=(await db.execute(text("select id,account_key,transport from wa_accounts where account_key=:key and revoked_at is null limit 1"), {'key':default_key})).mappings().first()
        if row:
            return OutboundAccount(str(row['account_key']), str(row['id']), str(row['transport']))
    raise AccountRoutingError('no unambiguous active WhatsApp account for recipient')
