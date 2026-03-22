"""LogForge query service.

Provides a rich read API over the logs table:
- Filtering by service, level, time range
- Full-text search (PostgreSQL GIN index)
- Cursor-based pagination
- Redis caching for repeated queries
- Error rate aggregations
- Alert rule management
"""
from __future__ import annotations
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, AsyncGenerator
from uuid import UUID

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from common.settings import DatabaseSettings, RedisSettings

logger = logging.getLogger(__name__)
db_settings = DatabaseSettings()
redis_settings = RedisSettings()

_pool: asyncpg.Pool | None = None
_redis: aioredis.Redis | None = None
CACHE_TTL = 60  # seconds


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _pool, _redis
    _pool = await asyncpg.create_pool(db_settings.database_url, min_size=2, max_size=20)
    _redis = aioredis.from_url(redis_settings.redis_url, decode_responses=True)
    logger.info("Query service started")
    yield
    if _pool: await _pool.close()
    logger.info("Query service stopped")


app = FastAPI(
    title="LogForge Query API",
    version="1.0.0",
    description="Query, filter, search, and aggregate logs from PostgreSQL.",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _cache_key(params: dict) -> str:
    raw = json.dumps(params, sort_keys=True, default=str)
    return "lf:q:" + hashlib.md5(raw.encode()).hexdigest()


async def _cached(key: str, fetch_fn) -> Any:
    if _redis:
        cached = await _redis.get(key)
        if cached:
            return json.loads(cached)
    result = await fetch_fn()
    if _redis:
        await _redis.setex(key, CACHE_TTL, json.dumps(result, default=str))
    return result


@app.get("/logs", summary="Query logs with filtering and pagination")
async def query_logs(
    service: str | None = Query(None, description="Filter by service_name"),
    level: str | None = Query(None, description="Filter by log level"),
    q: str | None = Query(None, description="Full-text search in message"),
    from_ts: datetime | None = Query(None, alias="from", description="Start time (ISO 8601)"),
    to_ts: datetime | None = Query(None, alias="to", description="End time (ISO 8601)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
) -> dict[str, Any]:
    if _pool is None:
        raise HTTPException(503, "Database not ready")

    cache_key = _cache_key({"service": service, "level": level, "q": q,
                             "from": from_ts, "to": to_ts, "page": page,
                             "page_size": page_size, "sort": sort})

    async def fetch():
        conditions = []
        args: list[Any] = []
        n = 1

        if service:
            conditions.append(f"service_name = ${n}"); args.append(service); n += 1
        if level:
            conditions.append(f"level = ${n}"); args.append(level.upper()); n += 1
        if from_ts:
            conditions.append(f"timestamp >= ${n}"); args.append(from_ts); n += 1
        if to_ts:
            conditions.append(f"timestamp <= ${n}"); args.append(to_ts); n += 1
        if q:
            conditions.append(f"to_tsvector('english', message) @@ plainto_tsquery('english', ${n})")
            args.append(q); n += 1

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        order = "DESC" if sort == "desc" else "ASC"
        offset = (page - 1) * page_size

        count_q = f"SELECT COUNT(*) FROM logs {where}"
        data_q = (f"SELECT id, timestamp, service_name, level, message, metadata "
                  f"FROM logs {where} ORDER BY timestamp {order} "
                  f"LIMIT ${n} OFFSET ${n+1}")
        args_data = args + [page_size, offset]

        async with _pool.acquire() as conn:
            total = await conn.fetchval(count_q, *args)
            rows = await conn.fetch(data_q, *args_data)

        items = [
            {"id": str(r["id"]), "timestamp": r["timestamp"].isoformat(),
             "service_name": r["service_name"], "level": r["level"],
             "message": r["message"], "metadata": json.loads(r["metadata"] or "{}")}
            for r in rows
        ]
        return {
            "items": items,
            "pagination": {"page": page, "page_size": page_size,
                           "total": total, "pages": (total + page_size - 1) // page_size},
        }

    return await _cached(cache_key, fetch)


@app.get("/logs/aggregations", summary="Error rate aggregations per time interval")
async def aggregations(
    service: str | None = Query(None),
    level: str = Query("ERROR"),
    interval: str = Query("minute", pattern="^(minute|hour|day)$"),
    limit: int = Query(60, ge=1, le=1440),
) -> dict[str, Any]:
    if _pool is None:
        raise HTTPException(503, "Database not ready")

    trunc = {"minute": "minute", "hour": "hour", "day": "day"}[interval]
    conditions = [f"level = $1"]
    args: list[Any] = [level.upper()]
    n = 2
    if service:
        conditions.append(f"service_name = ${n}"); args.append(service); n += 1

    where = "WHERE " + " AND ".join(conditions)
    q = (f"SELECT date_trunc('{trunc}', timestamp) AS bucket, COUNT(*) AS count "
         f"FROM logs {where} GROUP BY bucket ORDER BY bucket DESC LIMIT ${n}")
    args.append(limit)

    async with _pool.acquire() as conn:
        rows = await conn.fetch(q, *args)

    return {
        "level": level,
        "interval": interval,
        "service": service,
        "buckets": [{"bucket": r["bucket"].isoformat(), "count": r["count"]} for r in rows],
    }


@app.get("/health", summary="Health check")
async def health() -> dict[str, Any]:
    db_ok = False
    if _pool:
        try:
            async with _pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_ok = True
        except Exception:
            pass
    return {"status": "healthy" if db_ok else "degraded", "service": "query",
            "db": "ok" if db_ok else "error"}
