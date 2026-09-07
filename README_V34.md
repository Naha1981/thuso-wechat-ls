# Naha SuperApp Backend v2.14 — Production Readiness

v2.14 is the platform-completion release for the core WhatsApp transaction engine.

## Key guarantees
- inbound WhatsApp events are durable before ACK
- processing is asynchronous with retries and leases
- outbound WhatsApp account routing is explicit or deterministically resolved
- ambiguous multi-account routing fails closed
- inbound identities are bound to their WhatsApp account
- trace IDs can flow from inbox to outbox
- production startup validates critical configuration
- existing commerce/payment/provider/delivery services remain transport-agnostic

## Complete vertical slice
Customer -> WhatsApp -> durable inbox -> identity -> command router -> order -> payment -> merchant -> delivery -> courier -> proof -> delivered -> settlement -> outbound receipt.

## Verification
Run `pytest -q` from the repository root. Live Postgres/Redis/WhatsApp/payment integration requires real infrastructure.
