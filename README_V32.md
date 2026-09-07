# Naha SuperApp Backend v2.12 — WhatsApp Operations & Observability

v2.12 adds the operational control plane around the WhatsApp transport.

## Operations API

All endpoints require an authenticated session with the `admin` role:

- `GET /api/v1/ops/whatsapp/overview`
- `GET /api/v1/ops/whatsapp/accounts`
- `GET /api/v1/ops/whatsapp/transport`
- `GET /api/v1/ops/whatsapp/failures`
- `POST /api/v1/ops/whatsapp/accounts/{wa_account_id}/reset-circuit`

The API exposes no credentials or QR payloads. It reports operational state only.

## Metrics

The overview reports:

- inbound received/processing/failed/dead-letter/processed counts
- average inbound processing time
- outbound pending/sent/delivered/read/failed counts
- active/revoked WhatsApp accounts
- healthy/degraded/circuit-open account health

## Account inspection

The transport endpoint queries the active WhatsApp transport for each active account. A transport failure is returned as an operational error instead of failing the whole dashboard response.

## Database

Migration `031_whatsapp_operations.sql` adds indexes for failure queues, stuck processing events, account health, failed outbound messages and receipt history.

## Security

Operations are protected by the existing session/auth boundary and `admin` role. Circuit reset is an explicit administrative action and is persisted before returning success.

## Verification

58 tests pass. Python compilation passes. Node/Baileys typecheck is not claimed unless dependencies are installed and verified.
