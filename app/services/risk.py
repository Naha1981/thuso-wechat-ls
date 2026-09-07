from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

class RiskDecision(StrEnum):
    ALLOW = 'allow'
    REVIEW = 'review'
    BLOCK = 'block'

@dataclass(frozen=True)
class RiskInput:
    amount: Decimal
    daily_amount: Decimal = Decimal('0')
    daily_count: int = 0
    failed_count: int = 0
    account_age_days: int = 0
    kyc_level: str = 'unverified'
    payout: bool = False
    new_destination: bool = False
    velocity_window_count: int = 0

@dataclass(frozen=True)
class RiskResult:
    score: int
    decision: RiskDecision
    reasons: tuple[str, ...]

def score_transaction(x: RiskInput) -> RiskResult:
    score = 0
    reasons: list[str] = []
    if x.amount > Decimal('5000'): score += 20; reasons.append('high_value')
    if x.amount > Decimal('20000'): score += 25; reasons.append('very_high_value')
    if x.daily_amount > Decimal('15000'): score += 20; reasons.append('daily_value_velocity')
    if x.daily_count >= 15: score += 15; reasons.append('daily_count_velocity')
    if x.velocity_window_count >= 5: score += 20; reasons.append('short_window_velocity')
    if x.failed_count >= 3: score += 15; reasons.append('repeated_failures')
    if x.account_age_days < 2: score += 15; reasons.append('new_account')
    if x.kyc_level == 'unverified': score += 20; reasons.append('unverified_customer')
    if x.payout and x.new_destination: score += 30; reasons.append('new_payout_destination')
    if x.payout and x.kyc_level != 'full': score += 20; reasons.append('payout_requires_full_kyc')
    if score >= 70: decision = RiskDecision.BLOCK
    elif score >= 40: decision = RiskDecision.REVIEW
    else: decision = RiskDecision.ALLOW
    return RiskResult(score, decision, tuple(reasons))
