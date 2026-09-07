# Naha SuperApp Backend v2.13 — Durable WhatsApp Processing

## Purpose

v2.13 completes the reliability boundary for inbound WhatsApp traffic. HTTP webhooks now acknowledge only after the event is durably persisted. Domain processing runs asynchronously from the durable inbox, with retries and stale-worker lease recovery.

## Inbound lifecycle

```text
WhatsApp
  -> transport/operator
  -> authenticated webhook
  -> whatsapp_inbox_events
  -> HTTP ACK
  -> inbox worker
  -> identity + conversation
  -> unified WhatsApp router
  -> transactional outbox
  -> WhatsApp transport
```

A duplicate transport event is rejected by the database uniqueness boundary and does not execute the domain command twice.

## Worker guarantees

- DB-backed inbox is the source of truth.
- Processing uses `FOR UPDATE SKIP LOCKED`.
- Failed events use bounded exponential retry.
- Eight processing attempts are allowed before `dead_letter`.
- Five-minute processing leases are reclaimable after a worker crash.
- Existing conversation/message deduplication remains as a second defense.
- Media registration stays at Baileys ingress so the operator can upload the received media bytes after the webhook ACK.

## Transport boundary

Meta Cloud and Baileys continue to feed the same domain router. Baileys remains the current production transport; Meta remains a disabled future transport contract until credentials and behavior are verified.

## Operations

v2.12 operations APIs continue to expose inbox/outbox failures, account health, transport status and circuit state.

## Verification

```text
61 passed
```

Python compilation passes. Live Supabase, Redis, WhatsApp and payment-provider integration tests require real infrastructure.
