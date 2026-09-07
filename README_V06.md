# Naha SuperApp Backend v0.6

WhatsApp transaction experience layered on the v0.5 Agent Core.

## v0.6
- Verified WhatsApp inbound parsing for text, location and interactive replies.
- Persistent agent sessions for location collection.
- Exact action previews with Confirm / Decline buttons.
- WhatsApp outbound messages go through transactional outbox storage.
- Outbox worker with retries and dead-letter (`failed`) state.
- Request status + offer visibility endpoints.
- Provider location updates.
- Offer expiry protection.
- Signed, idempotent payment webhook handling.
- Payment settlement posts to the wallet ledger only after signature verification.

## Run
Apply migrations 001 through 006, configure `.env`, then run `uvicorn app.main:app --reload`.
Run the outbound worker separately with `python -m app.services.outbox_worker`.
