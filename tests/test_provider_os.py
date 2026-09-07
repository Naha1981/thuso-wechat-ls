import pytest
from app.services.provider_os import parse_provider_command

def test_provider_command_parser():
    assert parse_provider_command('PROVIDER electrician Acme Electrical') == ('onboard', {'category':'electrician','business_name':'Acme Electrical'})
    assert parse_provider_command('JOBS') == ('offers', {})
    assert parse_provider_command('ONLINE') == ('online', {})
    assert parse_provider_command('COMPLETE 12345678-1234-1234-1234-123456789012 850.50')[0] == 'complete'
    assert parse_provider_command('hello') is None

def test_merchant_commands_are_distinct():
    from app.services.merchant_os import parse_merchant_command
    assert parse_merchant_command('ORDERS') == ('orders', {})
    assert parse_merchant_command('ACCEPT ORDER 12345678-1234-1234-1234-123456789012')[0] == 'accept'
    assert parse_merchant_command('READY ORDER 12345678-1234-1234-1234-123456789012')[0] == 'ready'
    assert parse_merchant_command('ADD ITEM Chicken Burger 45.00')[0] == 'add_item'
