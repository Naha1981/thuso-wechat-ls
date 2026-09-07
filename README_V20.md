# Naha SuperApp Backend v2.0 — Identity + Baileys WhatsApp Operator

v2.0 makes WhatsApp a first-class channel identity and replaces Meta Cloud API as the primary transport with the verified two-service Baileys architecture.

## Architecture

`Main FastAPI app -> HTTP/x-api-key -> standalone Node Baileys operator -> WhatsApp`

Both services share PostgreSQL. The operator owns exactly one live Baileys socket per WhatsApp account, persists credentials/Signal keys, stores the current QR, and forwards normalized inbound messages to the main app using HMAC `WEBHOOK_SECRET`.

The main app never imports Baileys and never opens a WhatsApp socket.

## Operator routes

- `GET /healthz`
- `GET /status/:accountKey`
- `POST /start` `{accountKey}`
- `POST /reset` `{accountKey}`
- `POST /send` `{accountKey?,to,type,...}`

All non-health routes require constant-time `x-api-key` authentication.

## Pairing/reconnect rules

- `fetchLatestBaileysVersion()` before every socket creation.
- QR is persisted to `wa_accounts` and refreshed by Baileys.
- Disconnect status is logged before stale-socket guards.
- Session credentials are purged only for `loggedOut` / `500` as specified by the reference architecture.
- Ordinary disconnects reconnect with exponential backoff + jitter without purging credentials.
- `connectionReplaced` is not allowed to create a second socket.
- Main app can poll `/status` every 3–5 seconds.

## Identity

A verified Baileys inbound message resolves:

`WhatsApp JID/account -> channel_identity -> users -> roles`

The system stores only hashes for internal bearer sessions and OTP codes.

## Production validation

Before calling pairing fixed:

1. Confirm the deployed operator commit is live.
2. Programmatically decode the actual QR if pairing fails.
3. Pull continuous logs for a full QR cycle.
4. Search logs for the actual pairing-success signal before changing code.
5. Verify byte-for-byte `DATABASE_URL`, `OPERATOR_API_KEY`, `WEBHOOK_SECRET`, and `MAIN_APP_WEBHOOK_URL` parity.
6. If QR is valid and `pair-success` never occurs across multiple cycles, test a clean WhatsApp number before making more code changes.
