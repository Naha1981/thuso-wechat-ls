from decimal import Decimal
from app.services.commerce import parse_commerce_command, money

def test_commerce_commands():
    assert parse_commerce_command('MENU') == ('menu', {})
    assert parse_commerce_command('CART') == ('cart', {})
    assert parse_commerce_command('MENU 00000000-0000-0000-0000-000000000001')[0] == 'merchant_menu'
    assert parse_commerce_command('CHECKOUT') == ('checkout', {})
    x=parse_commerce_command('ADD 2 3')
    assert x[0]=='add_index' and x[1]['index']==2 and x[1]['quantity']==Decimal('3')

def test_money_rounding():
    assert money('12.345') == Decimal('12.35')
