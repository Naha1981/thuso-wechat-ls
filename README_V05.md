# Naha SuperApp Backend v0.5

Transactional Agent Core. A confirmed agent action now executes against the service-request and dispatch engine in one database transaction.

## Flow
WhatsApp -> agent message -> pending action -> explicit confirmation -> service request -> provider offers -> outbox event -> receipt.

## Security model
- Actions are scoped to the authenticated user ID supplied by the API boundary; production deployments should derive this identity from a verified auth/session rather than trusting arbitrary client input.
- Consequential actions require explicit confirmation.
- Idempotency keys prevent duplicate agent actions.
- DB row locks protect action execution from concurrent confirmations.
- Payment execution is deliberately not automatic; payment providers must confirm settlement through signed webhooks before a ledger mutation.

## Migration
Run `005_agent_execution.sql` after migrations 001-004.
