# Naha SuperApp Backend v0.4 — Agent Core

Adds a WhatsApp-first agent layer above the execution engine.

## Principles
- Deterministic command parsing before model-based reasoning.
- LLMs may propose actions but do not receive payment authority by default.
- Consequential actions require explicit confirmation.
- Server-side risk policy, not the prompt, enforces action boundaries.
- Every future executed consequential action must create an immutable receipt.
- Mental-health responses are support-oriented and do not diagnose; crisis signals route to immediate human/emergency support language.

## API
POST `/api/v1/agent/messages`
POST `/api/v1/agent/confirm`

## Next integration
Wire approved actions to the v0.3 execution service, persist sessions/actions/receipts, add Redis rate limiting and outbox-driven WhatsApp delivery, then add provider and payment adapters.
