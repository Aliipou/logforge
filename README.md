# LogForge

Production-grade log analytics system. Real-time ingestion via Apache Kafka, structured storage in PostgreSQL, instant querying with full-text search and aggregations.

[![CI](https://github.com/Aliipou/logforge/actions/workflows/ci.yml/badge.svg)](https://github.com/Aliipou/logforge/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

## The Problem

Every production system generates logs. Without a structured pipeline, debugging means SSH-ing into servers and running `grep`. That doesn't scale past 3 services.

LogForge gives you a Kafka-backed ingestion buffer, a processor that writes to PostgreSQL with proper indexes, and a query API with filtering, pagination, full-text search, and error rate alerting — all running with one command.

## Architecture

```
Client
  │
  ▼
FastAPI Ingestion Service  ──► Kafka (logs-topic)
                                      │
                                      ▼
                              Processor Service
                                      │
                              ┌───────▼────────┐
                              │   PostgreSQL   │
                              │  (logs table)  │
                              └───────┬────────┘
                                      │
                              FastAPI Query API ◄── Client
                                      │
                              Redis (cache + rate limit)
```

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Pydantic |
| Message broker | Apache Kafka (via confluent-kafka) |
| Storage | PostgreSQL 16 + JSONB |
| Cache / Rate limit | Redis 7 |
| Containerization | Docker + Docker Compose |
| Testing | pytest + testcontainers |
| Linting | ruff + mypy |

## Quick Start

```bash
git clone https://github.com/Aliipou/logforge
cd logforge
docker compose up -d
```

The ingestion API is at `http://localhost:8001`, the query API at `http://localhost:8002`.

### Ingest a log

```bash
curl -X POST http://localhost:8001/logs \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "auth-service",
    "level": "ERROR",
    "message": "Invalid token — JWT signature verification failed",
    "metadata": {"user_id": 123, "ip": "1.2.3.4"}
  }'
```

### Query logs

```bash
# Filter by service and level
curl "http://localhost:8002/logs?service=auth-service&level=ERROR&page=1&page_size=20"

# Time range
curl "http://localhost:8002/logs?from=2024-01-15T00:00:00Z&to=2024-01-15T23:59:59Z"

# Full-text search
curl "http://localhost:8002/logs?q=JWT+signature"

# Error rate aggregation (per minute)
curl "http://localhost:8002/logs/aggregations?service=auth-service&interval=minute"
```

## Database Schema

```sql
CREATE TABLE logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    service_name TEXT NOT NULL,
    level       TEXT NOT NULL CHECK (level IN ('DEBUG','INFO','WARNING','ERROR','CRITICAL')),
    message     TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}'
);

-- Non-negotiable indexes
CREATE INDEX idx_logs_timestamp    ON logs(timestamp DESC);
CREATE INDEX idx_logs_service      ON logs(service_name);
CREATE INDEX idx_logs_level        ON logs(level);
CREATE INDEX idx_logs_service_ts   ON logs(service_name, timestamp DESC);
CREATE INDEX idx_logs_fts          ON logs USING gin(to_tsvector('english', message));
```

## Alerting

A background task checks error rates every 60 seconds. If `ERROR` or `CRITICAL` logs exceed a threshold within the window, an alert fires.

```
GET /alerts/rules       List configured alert rules
POST /alerts/rules      Create a new rule
GET /alerts/active      Active (unacknowledged) alerts
```

Default rule: `auth-service ERROR > 50/min → CRITICAL alert`.

## Services

### ingestion_service

Validates incoming log payloads and publishes to Kafka `logs-topic` keyed by `service_name` (ensures partition locality per service).

Does NOT write to PostgreSQL directly — Kafka provides the durability buffer.

### processor_service

Consumes from `logs-topic`, batch-inserts into PostgreSQL every 500ms or 100 records (whichever comes first). Failed records go to `logs-topic-dlq` (Dead Letter Queue) after 3 retries.

### query_service

Read API with:
- Filtering by `service_name`, `level`, time range, full-text
- Cursor-based pagination
- Redis caching (60s TTL on repeated queries)
- Rate limiting (100 req/min per IP)
- Error rate aggregations

## Running Tests

```bash
pip install -e ".[dev]"
make test           # unit + integration (requires Docker for testcontainers)
make test-unit      # unit only
make lint           # ruff + mypy
```

## License

MIT
