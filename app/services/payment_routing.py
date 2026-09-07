from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

@dataclass(frozen=True)
class RouteCandidate:
    provider: str
    channel: str
    fee_fixed: Decimal = Decimal('0')
    fee_rate: Decimal = Decimal('0')
    priority: int = 100
    healthy: bool = True
    available: bool = True
    supports_refund: bool = True
    supports_payout: bool = False
    max_amount: Decimal | None = None

@dataclass(frozen=True)
class RouteDecision:
    provider: str
    channel: str
    estimated_fee: Decimal
    score: Decimal
    fallback_providers: tuple[str, ...]
    reason: str

def estimate_fee(amount: Decimal, c: RouteCandidate) -> Decimal:
    return (c.fee_fixed + amount * c.fee_rate).quantize(Decimal('0.01'))

def rank_routes(amount: Decimal, candidates: Iterable[RouteCandidate]) -> list[tuple[RouteCandidate, Decimal, Decimal]]:
    ranked=[]
    for c in candidates:
        if not c.healthy or not c.available or (c.max_amount is not None and amount > c.max_amount):
            continue
        fee=estimate_fee(amount,c)
        # Lower score is better. Priority is a configurable business preference,
        # while fee is a smaller tie-breaker. No agent/model participates here.
        score=Decimal(c.priority) + fee
        ranked.append((c,fee,score))
    return sorted(ranked,key=lambda x:(x[2],x[0].provider,x[0].channel))

def choose_route(amount: Decimal, candidates: Iterable[RouteCandidate]) -> RouteDecision:
    ranked=rank_routes(amount,candidates)
    if not ranked:
        raise ValueError('no eligible payment route available')
    best,fee,score=ranked[0]
    fallbacks=tuple(x[0].provider for x in ranked[1:])
    return RouteDecision(best.provider,best.channel,fee,score,fallbacks,
        f'{best.provider}/{best.channel} selected by deterministic priority + estimated fee')
