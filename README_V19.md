# Naha SuperApp Backend v1.9 — Delivery & Logistics Engine

v1.9 turns delivery into a first-class domain instead of a generic service request.

## Delivery lifecycle

searching → assigned → at_pickup → picked_up → in_transit → delivered

Failure/cancellation are terminal states.

## Capabilities

- Delivery jobs linked to commerce orders and service requests
- Courier assignment
- Courier tracking points with PostGIS geography
- Customer delivery tracking API
- Proof-of-delivery records
- OTP/photo/signature/recipient-confirmation proof types
- Delivery failure and cancellation handling
- Provider offer notification through the outbox
- Customer status notifications through the outbox
- Delivery events and audit trail
- Merchant `READY` automatically creates a delivery job
- Existing Dispatch 2.0 ranking is reused for courier selection
- PostgreSQL remains source of truth; Redis/event infrastructure remains asynchronous

## Security boundary

The current delivery API is intentionally internal-session protected. Production deployment must replace the internal secret boundary with verified provider/customer sessions and authorization scoped to the delivery job. Proof hashes are stored as references; raw identity documents or sensitive credentials are not stored in the delivery domain.
