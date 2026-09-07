from __future__ import annotations
import httpx
from decimal import Decimal
from app.payments.providers.base import PaymentRequest, PaymentResult

class MoPayLesothoGateway:
    name='mopay_ls'; country='LS'; channels=('mpesa','ecocash','card')
    def __init__(self, *, base_url='https://mopay.co.ls', api_key='', webhook_secret='', timeout=20):
        self.base_url=base_url.rstrip('/'); self.api_key=api_key; self.webhook_secret=webhook_secret; self.timeout=timeout
    def capabilities(self): return {'collect':True,'refund':False,'webhooks':False,'status_query':True,'payout':False}
    async def initiate(self, request: PaymentRequest) -> PaymentResult:
        if not self.api_key: return PaymentResult(self.name,'configuration_required',raw={'reason':'MOPAY_API_KEY not configured'})
        payload={'amount':str(request.amount),'reference':request.reference,'redirectUrl':request.callback_url or '',
                 'description':f'Naha payment {request.reference}','notificationPhoneNumber':request.customer.phone}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r=await client.post(f'{self.base_url}/api/external/payment',json=payload,
                headers={'Authorization':f'Bearer {self.api_key}','Content-Type':'application/json','Idempotency-Key':request.payment_id})
            r.raise_for_status(); data=r.json()
        return PaymentResult(self.name,'pending',data.get('sessionId'),data.get('paymentUrl'),data)
    async def get_status(self, session_id:str)->dict:
        if not self.api_key: raise RuntimeError('MOPAY_API_KEY not configured')
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r=await client.get(f'{self.base_url}/api/external/session/v1/{session_id}',headers={'Authorization':f'Bearer {self.api_key}'})
            r.raise_for_status(); return r.json()
    async def refund(self,*args,**kwargs): return PaymentResult(self.name,'unsupported')
    def verify_webhook(self,body,signature): return False
    def parse_webhook(self,body): raise ValueError('MoPay integration uses server-side session verification; no webhook contract is assumed')
