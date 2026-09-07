from __future__ import annotations
import hashlib, hmac, json
from decimal import Decimal
import httpx
from app.payments.providers.base import PaymentRequest, PaymentResult

class GenericLesothoGateway:
    def __init__(self, *, name: str, base_url: str, api_key: str = '', webhook_secret: str = '', channels: tuple[str,...] = ('card',), timeout: float = 20):
        self.name=name; self.country='LS'; self.base_url=base_url.rstrip('/'); self.api_key=api_key; self.webhook_secret=webhook_secret; self.channels=channels; self.timeout=timeout
    def capabilities(self):
        return {'collect': True, 'refund': True, 'webhooks': True}
    async def initiate(self, request: PaymentRequest) -> PaymentResult:
        # Endpoint paths are deliberately configurable: partner contracts differ and must not be guessed.
        if not self.base_url or not self.api_key:
            return PaymentResult(self.name, 'configuration_required', raw={'reason':'gateway credentials/base URL not configured'})
        payload={'amount': str(request.amount), 'currency':request.currency, 'reference':request.reference, 'customer':{'phone':request.customer.phone,'name':request.customer.name}, 'callback_url':request.callback_url}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r=await client.post(f'{self.base_url}/payments', json=payload, headers={'Authorization':f'Bearer {self.api_key}','Idempotency-Key':request.payment_id})
            r.raise_for_status(); data=r.json()
        return PaymentResult(self.name, data.get('status','pending'), data.get('provider_reference') or data.get('id'), data.get('checkout_url'), data)
    async def refund(self, provider_reference: str, amount: Decimal, currency: str, reference: str) -> PaymentResult:
        if not self.base_url or not self.api_key: return PaymentResult(self.name,'configuration_required')
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r=await client.post(f'{self.base_url}/refunds', json={'provider_reference':provider_reference,'amount':str(amount),'currency':currency,'reference':reference}, headers={'Authorization':f'Bearer {self.api_key}','Idempotency-Key':reference})
            r.raise_for_status(); data=r.json()
        return PaymentResult(self.name,data.get('status','pending'),data.get('provider_reference') or data.get('id'),raw=data)
    def verify_webhook(self, body: bytes, signature: str | None) -> bool:
        if not self.webhook_secret or not signature: return False
        expected=hmac.new(self.webhook_secret.encode(),body,hashlib.sha256).hexdigest()
        supplied=signature.removeprefix('sha256=')
        return hmac.compare_digest(expected,supplied)
    def parse_webhook(self, body: bytes): return json.loads(body)
