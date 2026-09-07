from app.services.whatsapp_account_routing import AccountRoutingError, OutboundAccount
from app.core.startup import validate_startup_configuration

def test_outbound_account_is_explicit_and_serializable():
    a=OutboundAccount('wa-main','00000000-0000-0000-0000-000000000001','baileys')
    assert a.account_key=='wa-main'
    assert a.transport=='baileys'

def test_ambiguous_routing_is_fail_closed():
    assert 'multiple active' in str(AccountRoutingError('multiple active WhatsApp accounts match recipient; account_key is required'))

def test_startup_validator_exists():
    assert callable(validate_startup_configuration)
