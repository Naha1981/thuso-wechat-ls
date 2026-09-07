from __future__ import annotations
from app.payments.providers.generic_http import GenericLesothoGateway

# Integration contracts only: production credentials/endpoints must come from
# an approved issuer/aggregator agreement. Never fabricate a direct issuer API.
class MoPayLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='mopay_ls', channels=('mpesa','ecocash','card'), **kw)

class PayLesothoGateway(GenericLesothoGateway):
    # Pay Lesotho publicly advertises a unified Lesotho wallet gateway.
    # Its public materials currently confirm M-Pesa, EcoCash and card for API use,
    # while its POS materials also advertise C-Pay and MyWallet.
    def __init__(self, **kw): super().__init__(name='paylesotho', channels=('mpesa','ecocash','cpay','mywallet','card'), **kw)

class MPesaLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='mpesa_ls', channels=('mpesa',), **kw)

class EcoCashLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='ecocash_ls', channels=('ecocash',), **kw)

class KhetsiLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='khetsi_ls', channels=('khetsi',), **kw)

class CPayLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='cpay_ls', channels=('cpay',), **kw)

class SmartelMoneyLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='smartel_money_ls', channels=('mywallet',), **kw)

class ChaperoneMoneyLesotho(GenericLesothoGateway):
    def __init__(self, **kw): super().__init__(name='chaperone_ls', channels=('cpay',), **kw)
