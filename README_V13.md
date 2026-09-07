# Naha SuperApp Backend v1.3 — Payment Orchestration

v1.3 turns deterministic payment routing into server-led payment execution.

## Flow

Payment -> route policy -> provider attempt -> checkout/session -> server-side verification -> payment state -> settlement pipeline.

## Lesotho

MoPay is implemented against its documented hosted payment-session API: POST `/api/external/payment`, then server-side GET session verification. M-Pesa, EcoCash and card are exposed through MoPay. Direct provider adapters remain contract-based and are only activated when credentials/API contracts are supplied.

## Safety

Redirect query parameters are not trusted as proof of payment. Provider status is verified server-side. Provider API keys remain server-side. The agent never receives payment credentials or financial authority.

## Added

- MoPay production-shaped adapter using documented endpoints
- Payment orchestration service
- Route decision + payment attempt persistence
- Attempt numbering and audit trail
- MoPay status verification endpoint
- Deterministic fallback architecture
- Migration 013
- v1.3 API routes

## Tests

24 passed.
