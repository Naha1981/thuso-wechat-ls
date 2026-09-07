from decimal import Decimal
import pytest
from app.services.payment_routing import RouteCandidate, choose_route, estimate_fee

def test_choose_lowest_priority_then_fee():
    d=choose_route(Decimal('100'),[
        RouteCandidate('paylesotho','mpesa',fee_rate=Decimal('.02'),priority=10),
        RouteCandidate('mopay_ls','mpesa',fee_rate=Decimal('.01'),priority=20),
    ])
    assert d.provider=='paylesotho'
    assert d.channel=='mpesa'
    assert d.fallback_providers==('mopay_ls',)

def test_unhealthy_and_over_limit_are_excluded():
    with pytest.raises(ValueError):
        choose_route(Decimal('500'),[
            RouteCandidate('x','mpesa',healthy=False),
            RouteCandidate('y','mpesa',max_amount=Decimal('100')),
        ])

def test_fee_calculation():
    c=RouteCandidate('x','mpesa',fee_fixed=Decimal('2.00'),fee_rate=Decimal('.015'))
    assert estimate_fee(Decimal('100'),c)==Decimal('3.50')
