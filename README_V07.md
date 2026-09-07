# Naha SuperApp Backend v0.7 — Provider Operating System

v0.7 adds the provider side of the WhatsApp marketplace.

## Provider WhatsApp commands

- `PROVIDER electrician Acme Electrical` — start provider onboarding
- `BUSINESS Acme Electrical` — complete business name during onboarding
- `ONLINE` — become available for dispatch
- `OFFLINE` — pause availability
- `JOBS` — list open offers
- `ACCEPT <offer_id>` — accept a job
- `REJECT <offer_id>` — decline a job
- `START <request_id>` — start an accepted job
- `COMPLETE <request_id>` — complete an accepted job
- `EARNINGS` — view provider earnings

## Provider API

The HTTP provider endpoints are deliberately protected by `X-Internal-Secret` in v0.7. This is an integration boundary, not the final provider authentication mechanism. A production deployment should replace it with authenticated provider sessions/short-lived tokens while keeping authorization server-side.

## Payment and earnings

Provider earnings are created only after a verified payment webhook settles the customer payment. Job completion alone never creates withdrawable earnings.

## Migration

Apply `supabase/migrations/007_provider_os.sql` after migration 006.
