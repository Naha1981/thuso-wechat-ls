# Naha SuperApp Backend v1.5 — Reconciliation & Provider Payout Operations

v1.5 adds operational controls around settlement: reconciliation batches/items/exceptions, verified payout destinations, payout execution attempts and payout completion state transitions.

## Financial control model

Payment confirmation remains separate from settlement, and settlement remains separate from payout execution. External provider statements are treated as evidence to reconcile against Naha's internal records; they never overwrite the immutable journal.

## Lesotho payment context

The architecture keeps rails/provider adapters separate from accounting. CBL currently lists five mobile-money issuers, while local aggregators/gateways can expose multiple rails through one integration. The platform must only enable a rail after commercial onboarding, API credentials, compliance approval and production verification.

## New APIs

- `POST /api/v1/reconciliation/batches`
- `POST /api/v1/reconciliation/batches/{batch_id}/items`
- `POST /api/v1/reconciliation/batches/{batch_id}/close`
- `POST /api/v1/reconciliation/payout-destinations`
- `POST /api/v1/reconciliation/payouts/{payout_id}/execute`
- `POST /api/v1/reconciliation/payout-attempts/{attempt_id}/complete`

## Safety

No API in this milestone assumes that a provider payout succeeded merely because Naha requested it. A payout becomes `paid` only after a verified external completion event/reference is recorded by a provider adapter or operations process.
