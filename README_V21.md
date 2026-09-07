# Naha SuperApp Backend v2.1 — Unified WhatsApp Command Engine

v2.1 removes the last transport-specific command-routing split.

## Architecture

Both WhatsApp ingress paths now resolve to the same command service:

`Baileys Operator -> HMAC webhook -> identity resolution -> whatsapp_router -> domain services -> outbox -> Baileys Operator -> WhatsApp`

The legacy Meta webhook, where retained for migration/backward compatibility, uses the same router.

## Unified command surface

The router dispatches, in order:

1. Agent confirmation / decline actions
2. Merchant commands
3. Customer commerce commands
4. Provider/courier commands
5. General intelligent-system agent handling

This means a command such as `JOBS`, `ACCEPT <offer_id>`, `MENU`, `CART`, `CHECKOUT`, `READY`, `ONLINE`, etc. behaves identically regardless of which WhatsApp ingress adapter delivered the message.

## Security properties

- Baileys ingress is authenticated with HMAC `WEBHOOK_SECRET`.
- Inbound message deduplication is performed before domain execution.
- WhatsApp sender identity is resolved through `channel_identities`; no inbound payload can select an arbitrary `user_id`.
- Outbound messages remain behind the Operator's constant-time `x-api-key` boundary.
- Consequential agent actions continue to use explicit confirmation and produce an action result.

## Validation

- Python compile: passed.
- Existing regression suite: **40 passed**.
- Operator TypeScript validation still requires installing the declared npm dependencies and running `npm run typecheck` in the operator service environment.

## Next hardening

v2.2 should make delivery/courier operations first-class WhatsApp commands, add operator account administration, enforce proof-of-delivery policy before `delivered`, and replace remaining direct `provider_id`/`courier_id` API parameters with authenticated role-scoped principals.
