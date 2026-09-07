from decimal import Decimal
from app.services.financial import money

def test_money_rounding(): assert money('12.345') == Decimal('12.35')
def test_fee_math():
 subtotal=money('1000'); fee=money(subtotal*Decimal('0.10')); earning=money(subtotal-fee)
 assert fee==Decimal('100.00'); assert earning==Decimal('900.00')
