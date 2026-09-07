# Naha SuperApp Backend v1.0 — Financial Transaction Engine

v1.0 establishes the financial control plane for marketplace transactions.

## Added
- pricing quotes with explicit platform fee/provider earning split
- quote expiry and acceptance
- payment intents with idempotency keys
- transaction/daily risk limits enforced server-side
- authorization/capture state transitions
- verified refund lifecycle
- disputes
- provider available balance and payout requests
- payment event/reconciliation tables
- financial migration `010_financial_transaction_engine.sql`

## Security model
The agent may propose a price/payment action, but cannot override pricing, risk limits, payment state transitions, refunds, or payouts. Financial state is changed only by server-side policy and verified payment-provider events.

## Migration order
Run migrations 001 through 010 in order.

## Important
The included financial provider boundary is intentionally provider-neutral. A real payment adapter/webhook verifier must be connected before production money movement. Never treat a client-side success response as settlement.
