from __future__ import annotations
import os
from app.payments.providers.lesotho import *
from app.payments.providers.mopay import MoPayLesothoGateway

class PaymentRegistry:
    def __init__(self):
        self._providers={
            'mopay_ls': MoPayLesothoGateway(base_url=os.getenv('MOPAY_BASE_URL','https://mopay.co.ls'),api_key=os.getenv('MOPAY_API_KEY',''),webhook_secret=os.getenv('MOPAY_WEBHOOK_SECRET','')),
            'paylesotho': PayLesothoGateway(base_url=os.getenv('PAYLESOTHO_BASE_URL',''),api_key=os.getenv('PAYLESOTHO_API_KEY',''),webhook_secret=os.getenv('PAYLESOTHO_WEBHOOK_SECRET','')),
            'mpesa_ls': MPesaLesotho(base_url=os.getenv('MPESA_LS_BASE_URL',''),api_key=os.getenv('MPESA_LS_API_KEY',''),webhook_secret=os.getenv('MPESA_LS_WEBHOOK_SECRET','')),
            'ecocash_ls': EcoCashLesotho(base_url=os.getenv('ECOCASH_LS_BASE_URL',''),api_key=os.getenv('ECOCASH_LS_API_KEY',''),webhook_secret=os.getenv('ECOCASH_LS_WEBHOOK_SECRET','')),
            'khetsi_ls': KhetsiLesotho(base_url=os.getenv('KHETSI_BASE_URL',''),api_key=os.getenv('KHETSI_API_KEY',''),webhook_secret=os.getenv('KHETSI_WEBHOOK_SECRET','')),
            'cpay_ls': CPayLesotho(base_url=os.getenv('CPAY_BASE_URL',''),api_key=os.getenv('CPAY_API_KEY',''),webhook_secret=os.getenv('CPAY_WEBHOOK_SECRET','')),
            'smartel_money_ls': SmartelMoneyLesotho(base_url=os.getenv('SMARTEL_BASE_URL',''),api_key=os.getenv('SMARTEL_API_KEY',''),webhook_secret=os.getenv('SMARTEL_WEBHOOK_SECRET','')),
            'chaperone_ls': ChaperoneMoneyLesotho(base_url=os.getenv('CHAPERONE_BASE_URL',''),api_key=os.getenv('CHAPERONE_API_KEY',''),webhook_secret=os.getenv('CHAPERONE_WEBHOOK_SECRET','')),
        }
    def get(self,name):
        try:return self._providers[name]
        except KeyError: raise KeyError(f'unknown payment provider: {name}')
    def list(self): return [{'name':p.name,'country':p.country,'channels':p.channels,'capabilities':p.capabilities()} for p in self._providers.values()]

_registry=PaymentRegistry()
def get_payment_registry(): return _registry
