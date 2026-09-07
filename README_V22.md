# Naha SuperApp Backend v2.2 — Delivery & Courier WhatsApp OS

v2.2 makes delivery operations first-class in the unified WhatsApp command engine.

## Courier commands
- `DELIVERIES` / `DELIVERY JOBS`
- `DELIVERY <job_id>`
- `AT PICKUP <job_id>`
- `PICKED UP <job_id>`
- `IN TRANSIT <job_id>`
- `PROOF <job_id> <otp|photo|signature|recipient_confirmation> [proof_ref]`
- `DELIVERED <job_id>`

## Customer command
- `CONFIRM DELIVERY <job_id>` records recipient confirmation for the customer's own order.

## Safety
- Only providers in category `delivery` use courier commands.
- Courier ownership is checked by `courier_provider_id`.
- Delivery state transitions remain locked and deterministic.
- `DELIVERED` now fails closed unless a proof record exists.
- Every delivery state/proof action emits a delivery event and transactional outbox event.

## Next hardening
v2.3 should add media ingestion to the Baileys operator/main app contract so actual WhatsApp photos, documents, and voice notes can be safely stored as content-addressed objects and used for delivery proof, KYC, receipts, and future commerce workflows.
