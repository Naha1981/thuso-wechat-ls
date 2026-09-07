from __future__ import annotations
from app.payments.providers.generic_http import GenericLesothoGateway

# These are integration contracts, not fabricated direct APIs. Production credentials/endpoints
# are supplied after a commercial/technical agreement with the issuer or aggregator.
class MoPayLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='mopay_ls', channels=('mpesa','ecocash','card'), **kw)

class PayLesothoGateway(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='paylesotho', channels=('mpesa','ecocash','card'), **kw)

class MPesaLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='mpesa_ls', channels=('mpesa',), **kw)

class EcoCashLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='ecocash_ls', channels=('ecocash',), **kw)

class KhetsiLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='khetsi_ls', channels=('khetsi',), **kw)

class CPayLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='cpay_ls', channels=('cpay',), **kw)

class SmartelMoneyLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='smartel_money_ls', channels=('smartel_money',), **kw)

class ChaperoneMoneyLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='chaperone_ls', channels=('chaperone',), **kw)
