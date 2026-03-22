"""Redis-backed sliding window rate limiter for the ingestion API."""
from __future__ import annotations
import time
import redis.asyncio as aioredis


class RedisRateLimiter:
    """Token bucket rate limiter backed by Redis sorted sets.

    Uses a sliding window: counts requests in the last `window` seconds.
    Each unique key (IP address) gets its own window.
    """

    def __init__(self, redis_url: str, limit: int = 100, window: int = 60) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._limit = limit
        self._window = window

    async def is_allowed(self, key: str) -> bool:
        """Returns True if the request is within the rate limit."""
        now = time.time()
        window_start = now - self._window
        redis_key = f"rl:{key}"

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {str(now): now})
        pipe.expire(redis_key, self._window + 1)
        results = await pipe.execute()

        count = results[1]
        return count < self._limit
