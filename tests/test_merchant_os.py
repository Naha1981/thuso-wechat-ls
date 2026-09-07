from decimal import Decimal
from app.services.merchant_os import parse_merchant_command

def test_merchant_commands():
    assert parse_merchant_command('ORDERS') == ('orders', {})
    assert parse_merchant_command('ORDER 00000000-0000-0000-0000-000000000001')[0] == 'order'
    assert parse_merchant_command('REJECT ORDER 00000000-0000-0000-0000-000000000001 no stock')[1]['reason'] == 'no stock'
    assert parse_merchant_command('STOCK 00000000-0000-0000-0000-000000000001 12.5')[1]['quantity'] == '12.5'

def test_merchant_order_action_parser():
    assert parse_merchant_command('COMPLETE ORDER 00000000-0000-0000-0000-000000000001')[0] == 'complete'
    assert parse_merchant_command('CANCEL 00000000-0000-0000-0000-000000000001')[0] == 'cancel'
