# Naha SuperApp Backend v1.4 — Settlement & Ledger Engine

v1.4 adds a financial settlement control plane on top of the provider-neutral payment orchestration layer.

## Core capabilities
- Immutable financial journal and double-entry journal lines.
- Payment settlement allocation: gross -> platform revenue + provider payable.
- Provider balance reserves to prevent double-spending of earnings.
- Payout execution attempt tracking.
- Reconciliation batch primitives.
- Idempotent settlement by payment reference.

## Important boundary
Payment capture remains provider-confirmed. Settlement does not trust client redirects as proof of payment. Provider APIs/webhooks must establish `payments.status='paid'` before settlement.

## Lesotho architecture
The payment engine remains provider-neutral and country-aware. Lesotho mobile-money issuers are configured as regulated rails/providers rather than hard-coded into accounting logic. The Central Bank of Lesotho currently lists five licensed mobile-money issuers and oversees national payment systems.

## Production hardening still required
- Connect each licensed/provider rail only after partner API credentials and contracts are obtained.
- Replace placeholder payout adapter with a verified provider-specific payout implementation.
- Add accounting controls/reconciliation against provider statements.
- Apply authenticated principal/role checks to financial endpoints.
