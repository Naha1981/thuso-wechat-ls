# Naha SuperApp Backend v2.8 — Production Identity & Authorization Boundary

v2.8 hardens the API boundary so authenticated principals, not caller-supplied IDs, determine authority.

## Core rule

`Bearer session -> user_id -> role/scope -> domain authorization -> action`

Public/customer endpoints derive `user_id` from the authenticated session. Provider, merchant and courier operations derive the actor from the authenticated session and verify ownership or an explicit scoped role. Dispatcher/admin operations require explicit roles.

## Changes

- Added `app/core/principal.py` with user, provider, merchant, request and courier authorization helpers.
- Reworked delivery HTTP API to require authenticated sessions and derive courier provider IDs from the session.
- Reworked dispatch API to require dispatcher/admin roles; provider location requires provider ownership/scoped role.
- Reworked execution API to require authenticated customer/provider principals and scoped access.
- Reworked financial API so customer IDs are derived from sessions and provider/payment access is checked.
- Reworked commerce API so cart checkout and order access use the authenticated user.
- Reworked platform API so provider onboarding and service requests use the authenticated principal.
- Added authorization indexes in migration `027_authorization_boundary.sql`.
- Kept the standalone Baileys operator architecture unchanged; WhatsApp remains a transport boundary that can later be replaced by Meta Cloud API.

## Compatibility

Legacy request-body `user_id` / `owner_user_id` fields remain optional in schemas for client compatibility, but the API no longer trusts them as the acting principal.

## Verification

- Python compile: PASS
- Tests: **53 passed**
- Live database/API integration: not claimed; production credentials/services are not available in this environment.
- Node/Baileys typecheck: not claimed unless dependencies are installed and `tsc --noEmit` is actually run.
