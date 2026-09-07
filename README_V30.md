# Naha SuperApp Backend v2.10 — WhatsApp Transport Abstraction

v2.10 establishes a hard transport boundary. Baileys remains the active transport today. A future official Meta Cloud API transport can replace it without changing agent, identity, commerce, payments, delivery, media, or memory domains.

## Contract

`app/services/whatsapp_transport.py` defines `WhatsAppTransport` with:

- start_account
- status
- reset_account
- send_text
- send_buttons
- request_location
- capabilities

`BaileysTransport` delegates to the standalone operator. `MetaCloudTransport` is intentionally disabled until explicitly configured; it does not pretend to be production-ready before credentials and API behavior are verified.

## Account routing

`wa_accounts.transport` identifies the transport for each account. Outbound sends require an explicit account key; there is no arbitrary first-socket fallback.

## Inbound contract

The existing normalized inbound envelope remains transport-neutral:

`event -> account -> normalized message -> identity -> domain router`.

Baileys and future Meta webhooks should produce the same normalized message contract before entering the domain layer.

## Migration

`029_whatsapp_transport_abstraction.sql`

Adds transport metadata and transport event audit records.

## Verification

- Python compilation: PASS
- Tests: 56 passed
- Live Meta API integration: not claimed
- Node/Baileys typecheck: not claimed unless dependencies are installed and actually checked
