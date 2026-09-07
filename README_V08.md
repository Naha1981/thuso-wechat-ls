# Naha SuperApp Backend v0.8 — Marketplace Intelligence + Dispatch 2.0

v0.8 upgrades dispatch from nearest-provider lookup to a deterministic, auditable marketplace dispatch engine.

## Dispatch score

Provider ranking combines:
- distance
- rating
- response rate
- presence freshness
- completed-job experience
- ETA when available

The score is calculated server-side. The agent cannot change dispatch weights or bypass provider eligibility.

## Waves and recovery

Jobs are offered in dispatch waves with short offer expiry. Expired offers can trigger reassignment. `dispatch_attempts` provides an operational audit trail.

## Provider location

`PUT /api/v1/dispatch/providers/{provider_id}/location` updates the provider's PostGIS location and presence timestamp.

## APIs

- `POST /api/v1/dispatch/requests/{request_id}/run`
- `POST /api/v1/dispatch/requests/{request_id}/reassign`
- `POST /api/v1/dispatch/offers/expire`
- `PUT /api/v1/dispatch/providers/{provider_id}/location`

These endpoints currently use the database dependency and are intended to sit behind authenticated internal/provider authorization before public exposure.

## Migration

Apply `supabase/migrations/008_dispatch_intelligence.sql` after migration 007.
