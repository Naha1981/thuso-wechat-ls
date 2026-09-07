from decimal import Decimal
import pytest
from app.services.settlement import split_settlement, SettlementError

def test_split_settlement():
    assert split_settlement(Decimal('1000'),Decimal('100')) == (Decimal('1000.00'),Decimal('100.00'),Decimal('900.00'))

def test_split_rejects_fee_over_gross():
    with pytest.raises(SettlementError): split_settlement(Decimal('100'),Decimal('101'))
