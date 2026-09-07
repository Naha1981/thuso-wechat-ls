# Naha SuperApp Backend v0.9

## Real-Time Marketplace Event Pipeline

v0.9 adds a durable event-relay layer between the transactional PostgreSQL outbox and Redis Streams.

### Flow

```text
API / Service transaction
        |
        v
PostgreSQL outbox_events
        |
        v
Outbox relay worker
        |
        v
Redis Stream: naha:marketplace:events
        |
        +--> marketplace consumers
        +--> notification workers
        +--> dispatch workers
        +--> analytics / telemetry
```

### Guarantees

- Domain changes are written transactionally with an outbox event.
- Events are relayed to Redis only after the database transaction commits.
- Redis Streams provide durable, replayable delivery rather than fire-and-forget pub/sub.
- Consumer groups allow horizontal worker scaling.
- Event publication is recorded in `marketplace_event_log`.
- Dispatch leases prevent concurrent workers from racing the same service request.
- Relay failures use bounded retry/backoff and eventually enter a failed state for operational review.

### New migration

`009_realtime_marketplace.sql`

Adds:

- outbox event processing state
- event retry metadata
- dispatch leases
- marketplace event delivery log

### Worker

Run the relay with:

```bash
python -m app.services.realtime_worker
```

The worker can also be imported and scheduled by a process supervisor. Keep the relay and business consumers independently scalable.

### Important boundary

Redis is a transport and coordination layer, not the system of record. PostgreSQL remains authoritative for requests, offers, providers, payments, and ledger state.

Consumers must be idempotent because at-least-once delivery is intentional.
