from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, Any

@dataclass(frozen=True)
class PaymentCustomer:
    user_id: str
    phone: str
    name: str | None = None

@dataclass(frozen=True)
class PaymentRequest:
    payment_id: str
    amount: Decimal
    currency: str
    reference: str
    customer: PaymentCustomer
    callback_url: str | None = None

@dataclass(frozen=True)
class PaymentResult:
    provider: str
    status: str
    provider_reference: str | None = None
    checkout_url: str | None = None
    raw: dict[str, Any] | None = None

class PaymentProvider(Protocol):
    name: str
    country: str
    channels: tuple[str, ...]
    def capabilities(self) -> dict[str, bool]: ...
    async def initiate(self, request: PaymentRequest) -> PaymentResult: ...
    async def refund(self, provider_reference: str, amount: Decimal, currency: str, reference: str) -> PaymentResult: ...
    def verify_webhook(self, body: bytes, signature: str | None) -> bool: ...
    def parse_webhook(self, body: bytes) -> dict[str, Any]: ...
