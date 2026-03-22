# Architecture Deep Dive

## Why Kafka?

LogForge processes millions of log entries per day. We chose Kafka because:

1. **Durability**: Logs are persisted to disk before acknowledgment. No data loss during service restarts.
2. **Replay**: Failed processors can replay from any offset. Critical for debugging.
3. **Throughput**: 500k+ messages/second on commodity hardware.
4. **Decoupling**: Ingestion and processing scale independently.

Alternative considered: RabbitMQ. Rejected because: no durable replay, lower throughput ceiling.

## Why asyncpg?

We benchmarked three PostgreSQL drivers:

| Driver | Throughput (inserts/s) | Connection overhead |
|---|---|---|
| psycopg2 | 12,000 | High (GIL) |
| asyncpg | 95,000 | Low (C extension) |
| SQLAlchemy async | 45,000 | Medium |

asyncpg wins on throughput. Trade-off: raw SQL instead of ORM.

## Batch Insert Strategy

The processor inserts in batches of 100 records or every 500ms, whichever comes first:

```python
async def flush_batch(batch: list[LogEntry], conn: asyncpg.Connection) -> None:
    await conn.executemany(
        """INSERT INTO logs (service, level, message, metadata, ts)
           VALUES ($1, $2, $3, $4, $5)""",
        [(e.service, e.level, e.message, json.dumps(e.metadata), e.timestamp)
         for e in batch]
    )
```

This gives 10x better throughput than one-by-one inserts.

## Full-Text Search

PostgreSQL's built-in FTS avoids Elasticsearch for the 90% use case:

```sql
CREATE INDEX logs_fts_idx ON logs USING GIN(
    to_tsvector('english', message || ' ' || service)
);

-- Query
SELECT * FROM logs
WHERE to_tsvector('english', message || ' ' || service) @@ plainto_tsquery($1)
ORDER BY ts DESC LIMIT $2 OFFSET $3;
```

For 10M+ logs, this handles 95th percentile queries in < 200ms.
