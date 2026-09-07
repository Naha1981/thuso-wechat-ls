from decimal import Decimal
from app.services.risk import RiskInput,RiskDecision,score_transaction

def test_low_risk_allows():
    r=score_transaction(RiskInput(amount=Decimal('100'),kyc_level='verified',account_age_days=30))
    assert r.decision == RiskDecision.ALLOW

def test_velocity_triggers_review():
    r=score_transaction(RiskInput(amount=Decimal('6000'),daily_amount=Decimal('16000'),daily_count=15,kyc_level='verified',account_age_days=10))
    assert r.decision in (RiskDecision.REVIEW,RiskDecision.BLOCK)

def test_new_payout_destination_blocks_when_combined():
    r=score_transaction(RiskInput(amount=Decimal('25000'),payout=True,new_destination=True,kyc_level='basic',account_age_days=0))
    assert r.decision == RiskDecision.BLOCK

def test_reasons_are_deterministic():
    a=score_transaction(RiskInput(amount=Decimal('6000'),kyc_level='unverified'))
    b=score_transaction(RiskInput(amount=Decimal('6000'),kyc_level='unverified'))
    assert a == b
