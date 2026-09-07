from app.core.config import get_settings

async def allow(redis, key: str, limit: int | None = None, window: int = 60) -> bool:
    limit = limit or get_settings().rate_limit_per_minute
    bucket=f"rl:{key}"
    count=await redis.incr(bucket)
    if count == 1:
        await redis.expire(bucket, window)
    return count <= limit
