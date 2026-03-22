"""Unit tests for the Redis rate limiter (mocked Redis)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ingestion_service.rate_limiter import RedisRateLimiter


class TestRedisRateLimiter:
    @pytest.fixture
    def limiter(self):
        with patch("ingestion_service.rate_limiter.aioredis.from_url"):
            return RedisRateLimiter(redis_url="redis://localhost", limit=5, window=60)

    @pytest.mark.asyncio
    async def test_allows_within_limit(self, limiter):
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[0, 3, True, True])
        limiter._redis.pipeline = MagicMock(return_value=mock_pipe)
        assert await limiter.is_allowed("192.168.1.1") is True

    @pytest.mark.asyncio
    async def test_blocks_at_limit(self, limiter):
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[0, 5, True, True])
        limiter._redis.pipeline = MagicMock(return_value=mock_pipe)
        assert await limiter.is_allowed("192.168.1.1") is False
