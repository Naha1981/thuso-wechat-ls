import pytest
from app.services.whatsapp_transport import BaileysTransport, MetaCloudTransport, TransportError, TransportCapabilities

class FakeClient:
    async def send_text(self, to, body, account_key): return {'ok': True, 'transport': 'baileys', 'account': account_key}
    async def send_buttons(self, to, body, buttons, account_key): return {'ok': True}
    async def request_location(self, to, body, account_key): return {'ok': True}
    async def start(self, account_key): return {'ok': True}
    async def status(self, account_key): return {'status': 'connected'}
    async def reset(self, account_key): return {'ok': True}

@pytest.mark.asyncio
async def test_baileys_transport_forwards_account_key():
    result = await BaileysTransport(FakeClient()).send_text('acct-1', '2711', 'hi')
    assert result['account'] == 'acct-1'

@pytest.mark.asyncio
async def test_meta_transport_is_explicitly_disabled():
    class S: pass
    with pytest.raises(TransportError):
        await MetaCloudTransport(S()).send_text('2711', 'hi', 'meta-1')

@pytest.mark.asyncio
async def test_baileys_capabilities_are_explicit():
    caps = await BaileysTransport(FakeClient()).capabilities('acct-1')
    assert isinstance(caps, TransportCapabilities)
    assert caps.media_send is True
