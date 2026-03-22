"""LogForge ingestion service.

Accepts log payloads via HTTP, validates them, and publishes to Kafka.
Does NOT write to PostgreSQL — Kafka is the durability layer.
"""
from __future__ import annotations
import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, AsyncGenerator

from confluent_kafka import Producer
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from common.models import KafkaMessage, LogEntry
from common.settings import KafkaSettings, RedisSettings
from ingestion_service.rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)
kafka_settings = KafkaSettings()
redis_settings = RedisSettings()

_producer: Producer | None = None
_rate_limiter: RedisRateLimiter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _producer, _rate_limiter
    _producer = Producer({
        "bootstrap.servers": kafka_settings.bootstrap_servers,
        "client.id": "logforge-ingestion",
        "acks": "all",
        "retries": 5,
        "retry.backoff.ms": 300,
        "compression.type": "lz4",
    })
    _rate_limiter = RedisRateLimiter(
        redis_url=redis_settings.redis_url,
        limit=redis_settings.rate_limit_per_minute,
        window=60,
    )
    logger.info("Ingestion service started")
    yield
    if _producer:
        _producer.flush(timeout=5)
    logger.info("Ingestion service stopped")


app = FastAPI(
    title="LogForge Ingestion API",
    version="1.0.0",
    description="Accepts log payloads and publishes to Kafka. Fast path — no DB writes.",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _delivery_report(err, msg) -> None:
    if err:
        logger.error("Kafka delivery failed: %s", err)
    else:
        logger.debug("Delivered to %s [%d] @ %d", msg.topic(), msg.partition(), msg.offset())


@app.post("/logs", status_code=status.HTTP_202_ACCEPTED,
          summary="Ingest a log entry",
          responses={202: {"description": "Accepted and queued to Kafka"},
                     429: {"description": "Rate limit exceeded"}})
async def ingest_log(entry: LogEntry, request: Request) -> dict[str, str]:
    client_ip = request.client.host if request.client else "unknown"

    if _rate_limiter and not await _rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {redis_settings.rate_limit_per_minute} req/min",
        )

    message = KafkaMessage(
        service_name=entry.service_name,
        level=entry.level,
        message=entry.message,
        metadata=entry.metadata,
        ingested_at=datetime.now(UTC).isoformat(),
    )

    if _producer is None:
        raise HTTPException(status_code=503, detail="Producer not ready")

    _producer.produce(
        topic=kafka_settings.topic,
        key=entry.service_name.encode(),
        value=message.model_dump_json().encode(),
        on_delivery=_delivery_report,
    )
    _producer.poll(0)

    return {"status": "accepted", "topic": kafka_settings.topic}


@app.get("/health", summary="Health check")
async def health() -> dict[str, Any]:
    return {"status": "healthy", "service": "ingestion", "version": "1.0.0"}
