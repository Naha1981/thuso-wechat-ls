# Naha SuperApp v2.11 — WhatsApp Reliability & Delivery Guarantees

## Goal
Harden the WhatsApp transport boundary with durable inbox events, idempotent outbound records, delivery receipts, retries, dead-letter handling, and account health state.

## Flow
WhatsApp → Baileys Operator → HMAC webhook → durable inbox → domain processing.

Outbound: domain outbox → transport → provider message id → receipt events → delivery receipt ledger.

## Reliability
- `whatsapp_inbox_events` is the durable inbound boundary.
- `outbox_messages.idempotency_key` supports explicit caller-level deduplication.
- `whatsapp_delivery_receipts` records transport receipts.
- `whatsapp_account_health` records failures and circuit-open state.
- Operator retries transient webhook failures three times.
- Operator ignores Baileys `messages.upsert` events with `requestId`, reducing exposure to known history-sync spoofing behavior.
- Automatic history sync is disabled for this WhatsApp operator until explicitly required.

## Baileys security note
Baileys disclosed a critical message/history spoofing issue affecting versions before 7.0.0-rc12 / 6.7.22. This build moves the operator dependency floor to `^7.0.0-rc12` and also drops `requestId` message-upserts. Verify the actual installed lockfile/version before production deployment.

## Verification
- Python compilation: passed.
- Tests: 57 passed.
- Node `tsc --noEmit`: not claimed because npm dependencies were not installed and verified in this environment.
