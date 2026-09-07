from decimal import Decimal
from app.services.payment_routing import RouteCandidate, choose_route

def test_routing_falls_back_in_order():
    d=choose_route(Decimal('100'),[
      RouteCandidate('mopay_ls','mpesa',priority=1),
      RouteCandidate('paylesotho','mpesa',priority=2),
      RouteCandidate('mpesa_ls','mpesa',priority=3)])
    assert d.provider=='mopay_ls'
    assert d.fallback_providers==('paylesotho','mpesa_ls')

def test_highest_priority_can_be_excluded_by_amount():
    d=choose_route(Decimal('1000'),[
      RouteCandidate('mopay_ls','mpesa',priority=1,max_amount=Decimal('500')),
      RouteCandidate('paylesotho','mpesa',priority=2)])
    assert d.provider=='paylesotho'
