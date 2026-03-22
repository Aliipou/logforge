"""LogForge processor service.

Consumes from Kafka, batch-inserts into PostgreSQL.
Implements retry logic and DLQ for failed records.
"""
from __future__ import annotations
import asyncio
import json
import logging
import signal
import sys
from datetime import UTC, datetime

import asyncpg
from confluent_kafka import Consumer, KafkaError, Producer

from common.models import KafkaMessage
from common.settings import DatabaseSettings, KafkaSettings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

kafka_settings = KafkaSettings()
db_settings = DatabaseSettings()

BATCH_SIZE = 100
BATCH_TIMEOUT_MS = 500
MAX_RETRIES = 3


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(db_settings.database_url, min_size=2, max_size=10)


async def batch_insert(pool: asyncpg.Pool, records: list[dict]) -> int:
    """Bulk insert log records. Returns count inserted."""
    rows = [
        (r["service_name"], r["level"], r["message"],
         json.dumps(r.get("metadata", {})), r.get("ingested_at", datetime.now(UTC).isoformat()))
        for r in records
    ]
    async with pool.acquire() as conn:
        await conn.executemany(
            """INSERT INTO logs (service_name, level, message, metadata, timestamp)
               VALUES ($1, $2, $3, $4::jsonb, $5::timestamptz)
               ON CONFLICT DO NOTHING""",
            rows,
        )
    return len(rows)


def send_to_dlq(producer: Producer, topic: str, raw_value: bytes, error: str) -> None:
    """Send a failed record to the Dead Letter Queue."""
    envelope = json.dumps({"error": error, "original": raw_value.decode(errors="replace")})
    producer.produce(topic=topic, value=envelope.encode())
    producer.poll(0)
    logger.warning("Sent record to DLQ: %s", error[:100])


async def run_processor() -> None:
    pool = await create_pool()
    consumer = Consumer({
        "bootstrap.servers": kafka_settings.bootstrap_servers,
        "group.id": kafka_settings.group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "max.poll.interval.ms": 30000,
    })
    dlq_producer = Producer({"bootstrap.servers": kafka_settings.bootstrap_servers})
    consumer.subscribe([kafka_settings.topic])

    batch: list[dict] = []
    last_flush = asyncio.get_event_loop().time()
    running = True

    def shutdown(sig, frame):
        nonlocal running
        logger.info("Shutdown signal received")
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logger.info("Processor started — consuming from %s", kafka_settings.topic)

    try:
        while running:
            msg = consumer.poll(timeout=0.1)
            now = asyncio.get_event_loop().time()

            if msg is not None:
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        logger.error("Kafka error: %s", msg.error())
                    continue

                for attempt in range(MAX_RETRIES):
                    try:
                        payload = KafkaMessage.model_validate_json(msg.value())
                        batch.append(payload.model_dump())
                        break
                    except Exception as exc:
                        if attempt == MAX_RETRIES - 1:
                            send_to_dlq(dlq_producer, kafka_settings.dlq_topic,
                                        msg.value(), str(exc))

            should_flush = (
                len(batch) >= BATCH_SIZE or
                (batch and (now - last_flush) * 1000 >= BATCH_TIMEOUT_MS)
            )

            if should_flush:
                try:
                    inserted = await batch_insert(pool, batch)
                    consumer.commit(asynchronous=False)
                    logger.info("Inserted %d records", inserted)
                except Exception as exc:
                    logger.exception("Batch insert failed: %s", exc)
                    for record in batch:
                        send_to_dlq(dlq_producer, kafka_settings.dlq_topic,
                                    json.dumps(record).encode(), str(exc))
                finally:
                    batch.clear()
                    last_flush = now

    finally:
        if batch:
            try:
                await batch_insert(pool, batch)
                consumer.commit(asynchronous=False)
            except Exception:
                logger.exception("Final flush failed")
        consumer.close()
        dlq_producer.flush()
        await pool.close()
        logger.info("Processor stopped cleanly")


if __name__ == "__main__":
    asyncio.run(run_processor())
