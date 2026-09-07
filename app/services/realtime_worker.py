from __future__ import annotations
import asyncio
import json
import os
import socket
from redis.asyncio import Redis
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.realtime import (
    STREAM, GROUP, MarketplaceEvent, claim_outbox_events, ensure_consumer_group, publish_event,
    mark_event_published, mark_event_failed,
)

async def relay_once(redis: Redis, limit: int = 50) -> int:
    async with SessionLocal() as db:
        events = await claim_outbox_events(db, limit)
        await db.commit()
    count = 0
    for event in events:
        try:
            stream_id = await publish_event(redis, MarketplaceEvent(
                event_id=event['id'], event_type=event['event_type'],
                aggregate_type=event['aggregate_type'], aggregate_id=event['aggregate_id'],
                payload=event['payload'] or {},
            ))
            async with SessionLocal() as db:
                await mark_event_published(db, event['id'], stream_id)
                await db.commit()
            count += 1
        except Exception as exc:
            async with SessionLocal() as db:
                await mark_event_failed(db, event['id'], str(exc))
                await db.commit()
    return count

async def run_relay(interval: float = 0.25) -> None:
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        while True:
            await relay_once(redis)
            await asyncio.sleep(interval)
    finally:
        await redis.aclose()

async def consume_forever(consumer: str | None = None) -> None:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    consumer = consumer or f"{socket.gethostname()}-{os.getpid()}"
    try:
        await ensure_consumer_group(redis)
        while True:
            messages = await redis.xreadgroup(GROUP, consumer, {STREAM: ">"}, count=50, block=5000)
            for _, entries in messages:
                for stream_id, fields in entries:
                    # v0.9 keeps consumption durable and observable. Business handlers are
                    # intentionally idempotent and can be added without changing the transport.
                    await redis.xack(STREAM, GROUP, stream_id)
    finally:
        await redis.aclose()

if __name__ == '__main__':
    asyncio.run(run_relay())
