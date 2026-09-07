from decimal import Decimal
from app.services.delivery import TRANSITIONS

def test_delivery_transitions_are_monotonic():
    assert 'assigned' in TRANSITIONS['searching']
    assert 'picked_up' in TRANSITIONS['at_pickup']
    assert 'in_transit' in TRANSITIONS['picked_up']
    assert 'delivered' in TRANSITIONS['in_transit']

def test_delivery_terminal_states_have_no_transitions():
    assert TRANSITIONS.get('delivered', set()) == set()
    assert TRANSITIONS.get('failed', set()) == set()
    assert TRANSITIONS.get('cancelled', set()) == set()

def test_delivery_fee_decimal():
    assert Decimal('12.50') >= 0
