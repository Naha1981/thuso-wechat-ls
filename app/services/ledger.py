from decimal import Decimal
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import LedgerEntry

async def balance(db: AsyncSession, user_id: UUID, currency: str = "ZAR") -> Decimal:
    credits = await db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(LedgerEntry.user_id==user_id, LedgerEntry.currency==currency, LedgerEntry.direction=="credit"))
    debits = await db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(LedgerEntry.user_id==user_id, LedgerEntry.currency==currency, LedgerEntry.direction=="debit"))
    return Decimal(credits) - Decimal(debits)

async def append(db: AsyncSession, user_id: UUID, direction: str, amount: Decimal, reference: str, currency="ZAR", metadata=None):
    if amount < 0: raise ValueError("amount must be non-negative")
    if direction not in {"credit","debit"}: raise ValueError("invalid direction")
    entry = LedgerEntry(user_id=user_id, direction=direction, amount=amount, currency=currency, reference=reference, metadata=metadata or {})
    db.add(entry)
    await db.flush()
    return entry
