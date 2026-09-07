# Naha SuperApp Backend v2.9 — WhatsApp Identity & Onboarding

v2.9 makes authenticated WhatsApp account pairing explicit while keeping WhatsApp transport isolated behind the standalone Baileys operator.

## Two identity paths

1. **Consumer identity:** an inbound WhatsApp message is proof of channel possession at the transport boundary. The main app resolves/binds `channel_identities` and creates/uses the Naha user.
2. **Platform/operator account pairing:** an authenticated Naha user can start a pairing session from the web/API. The main app creates an owned `wa_accounts` row, calls the standalone operator, and polls the pairing status/QR.

## API

- `POST /api/v1/identity/whatsapp/pair`
- `GET /api/v1/identity/whatsapp/pair/{onboarding_id}`
- `POST /api/v1/identity/whatsapp/pair/{onboarding_id}/cancel`

All pairing endpoints require a valid bearer session. The QR is only exposed to the authenticated owner of the onboarding session.

## Database

Migration `028_whatsapp_identity_onboarding.sql` adds ownership and lifecycle metadata to `wa_accounts` and creates:

- `whatsapp_onboarding_sessions`
- `whatsapp_identity_events`

## Operator hardening

`/send` now requires an explicit `accountKey`. It no longer falls back to an arbitrary first connected socket, preventing a multi-account deployment from sending a message through the wrong WhatsApp account.

## Future Meta migration

The Naha identity, authorization, agent, commerce, payment and delivery layers remain transport-neutral. A future Meta Cloud API adapter can replace Baileys without changing these domain layers.

## Verification

- Python compile: PASS
- Tests: 53 passed
- Live database/API integration: not claimed
- Node/Baileys typecheck: not claimed unless npm dependencies are installed and `tsc --noEmit` is actually run
