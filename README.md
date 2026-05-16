# LogForge

Every production system generates logs. Without a structured pipeline, debugging means SSH-ing into a server and running `grep` — which does not work when logs are spread across multiple service instances, when you need to answer "how many ERROR events did payment-service emit in the last 10 minutes?", or when you want to be paged before a problem becomes an outage.

Most log collectors write directly to a database on the ingestion path. Under burst load this creates backpressure on the ingest endpoint and can block request threads. LogForge separates the write path (Kafka, fire-and-forget) from the storage path (batch-inserted by a separate consumer), giving the ingestion HTTP endpoint a consistent sub-millisecond response time regardless of database load.

---

## Architecture

```
Client HTTP POST /logs
    |
    v
Ingestion Service (:8001)            -- FastAPI, validates payload, checks Redis rate limit
    |   acks=all, retries=5, lz4 compression
    |
    v
Kafka (logs-topic)                   -- durability layer; messages survive processor restarts
    |
    v
Processor Service                    -- confluent-kafka Consumer
    |   batch of 100 records OR 500 ms timeout, whichever comes first
    |   ON CONFLICT DO NOTHING for idempotent re-delivery
    |   failed records -> logs-topic-dlq
    v
PostgreSQL (logs table)
    |   GIN index on to_tsvector(message) for full-text search
    |   timestamp index for range queries
    v
Query Service (:8002)               -- FastAPI, read-only
    |   filtering by service/level/time range + full-text search
    |   cursor-based pagination, Redis cache (60 s TTL, MD5-keyed)
    |   error rate aggregations (date_trunc per minute/hour/day)
    v
Alerting Service                    -- background loop, polls every 60 s
        reads alert_rules from PostgreSQL
        counts matching events in each rule window
        deduplicates: skips if unacknowledged alert_event exists in same window
        writes alert_events; logs WARNING
```

Four separate processes map to four independent containers in Docker Compose. The DLQ (`logs-topic-dlq`) acts as a quarantine for records that fail validation or batch insert after 3 retries — inspectable without data loss.

---

## Key Design Decisions

**Kafka as the durability layer, not a synchronous database write.** The ingestion service writes to Kafka (`acks=all`) and returns HTTP 202 immediately. If PostgreSQL goes down, Kafka retains messages for 168 hours (configurable). A synchronous write to Postgres on the ingestion path would make the HTTP endpoint's latency and availability directly dependent on the database. Tradeoff: messages are "accepted" before they are queryable; there is an inherent lag between ingestion and visibility in the query API equal to the batch flush interval (100 records or 500 ms).

**Batch insert with `ON CONFLICT DO NOTHING`, not per-record inserts.** The processor accumulates up to 100 records before calling `executemany`. A single round-trip for 100 rows is roughly 50x faster than 100 individual inserts. `ON CONFLICT DO NOTHING` makes re-delivery safe when the processor restarts after a commit but before Kafka offset commit. Tradeoff: a failed batch sends all 100 records to the DLQ, which may include some records that were actually valid.

**Redis sorted-set sliding window for rate limiting, not a token bucket in memory.** The `RedisRateLimiter` uses `ZADD` + `ZREMRANGEBYSCORE` + `ZCARD` in a pipeline to count requests in the last N seconds per IP. This survives ingestion service restarts and would work correctly with multiple ingestion service replicas. A purely in-memory counter would reset on restart and give each replica an independent limit. Tradeoff: every ingest request pays one Redis round-trip.

**Alerting as a polling loop, not a streaming trigger.** The alerting service runs a `SELECT COUNT(*)` against the `logs` table every 60 seconds. A streaming approach (Kafka Streams or a trigger-based mechanism) would add latency detection within seconds, but requires either a Kafka Streams cluster or a PostgreSQL LISTEN/NOTIFY integration. The polling approach is simple, correct, and the 60-second resolution is acceptable for most alert latency requirements. Tradeoff: alerts can fire up to 60 seconds after a threshold is crossed.

**Query caching with MD5-keyed Redis entries, not HTTP-level caching.** Query parameters (service, level, time range, page) are serialized and MD5-hashed to form the cache key. This gives per-query granularity: a query for `service=payments&level=ERROR` is cached independently from `service=auth&level=ERROR`. HTTP-level caching (ETags, Cache-Control) would require clients to implement conditional GET. Tradeoff: stale results for up to 60 seconds after new logs arrive that match the query.

---

## Tech Stack

| Component | Justification |
|---|---|
| **Kafka (Confluent Platform)** | Durable message queue; decouples ingest latency from storage latency; 168-hour log retention |
| **confluent-kafka** | Official Confluent Python client; lower-level than kafka-python but more stable for production use |
| **FastAPI** | Async endpoints for both ingestion and query services; automatic validation via Pydantic models |
| **asyncpg** | PostgreSQL async driver for the query service; connection pooling with configurable min/max size |
| **PostgreSQL 16** | Primary storage; GIN index on `to_tsvector(message)` enables full-text search; `date_trunc` for aggregations |
| **Redis 7** | Rate limiter (sorted sets, ingestion service) and query cache (query service, separate DB index) |
| **Pydantic v2** | Shared `LogEntry` and `KafkaMessage` models validated at ingestion boundary; `model_validate_json` in processor |
| **pydantic-settings** | Per-service `BaseSettings` classes with env-prefix isolation (`KAFKA_`, `DATABASE_`, `REDIS_`) |
| **testcontainers** | Integration tests spin up real Kafka, Postgres, and Redis containers; no mocking of infrastructure |

---

## Running Locally

```bash
git clone https://github.com/Aliipou/logforge.git
cd logforge

# Install dependencies (all services share one pyproject.toml)
pip install -e ".[dev]"

# Start all infrastructure and services
docker compose up

# Services:
#   Ingestion API:  http://localhost:8001
#   Query API:      http://localhost:8002
#   Kafka:          localhost:9092
#   PostgreSQL:     localhost:5432
#   Redis:          localhost:6379

# Ingest a log entry
curl -X POST http://localhost:8001/logs \
  -H "Content-Type: application/json" \
  -d '{"service_name": "payments", "level": "ERROR", "message": "charge failed", "metadata": {"user_id": 42}}'

# Query logs
curl "http://localhost:8002/logs?service=payments&level=ERROR&page_size=10"

# Full-text search
curl "http://localhost:8002/logs?q=charge+failed"

# Error rate aggregation by minute
curl "http://localhost:8002/logs/aggregations?service=payments&level=ERROR&interval=minute"
```

Run tests:

```bash
# Unit tests (no external services)
pytest tests/unit/ -v

# Integration tests (Docker required — testcontainers starts Kafka/Postgres/Redis)
pytest tests/integration/ -v
```

---

## Deployment

- **Zookeeper + Kafka** — required; `docker-compose.yml` uses `confluentinc/cp-kafka:7.6.0` with health checks ensuring Kafka is ready before the processor starts
- **PostgreSQL 16** — the `common/sql/init.sql` file creates the `logs`, `alert_rules`, and `alert_events` tables with indexes; it is mounted as a Docker init script
- **Redis 7** — two logical databases used: index 0 for ingestion rate limiter, index 1 for query cache
- **Four containers** — ingestion, processor, query, alerting run as separate services in `docker-compose.yml`; each has `restart: unless-stopped`
- **DLQ monitoring** — `logs-topic-dlq` should be monitored; high DLQ volume indicates schema mismatches or systematic Postgres write failures

Environment variables follow per-service prefixes:

```
KAFKA_BOOTSTRAP_SERVERS    # for ingestion and processor
KAFKA_TOPIC                # default: logs-topic
DATABASE_URL               # for processor, query, alerting
REDIS_URL                  # for ingestion (rate limiter) and query (cache)
RATE_LIMIT_PER_MINUTE      # default: 100
```

---

## Known Limitations / TODO

- **No authentication on ingestion or query endpoints.** Any client with network access can POST logs or read all logs. Add an API key or JWT middleware before exposing either service publicly.
- **Single Kafka partition / single broker.** `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1` and one broker means no fault tolerance. A production setup needs at minimum 3 brokers and replication factor 2.
- **Alert delivery is log-only.** The alerting service writes `WARNING` log lines and `alert_events` rows; it does not send Slack messages, emails, or webhook calls. The delivery integration is TODO.
- **No schema registry.** The Kafka message format (`KafkaMessage` Pydantic model) is shared via a Python import. If the schema changes, producer and consumer must be deployed together. A schema registry (Confluent Schema Registry or Apicurio) would enforce compatibility at the Kafka level.
- **Batch insert DLQ granularity.** A failed batch sends all records in the batch to the DLQ, including ones that may have been individually valid. Per-record retry before DLQ would require restructuring the processor loop.
- **No retention policy.** The `logs` table grows without bound. Add a `pg_partman` partition schedule or a periodic `DELETE WHERE timestamp < NOW() - INTERVAL` job.
