# Architecture

## Why Kafka?

Direct DB writes from the ingestion API create backpressure coupling: if PostgreSQL is slow or down, ingestion fails. Kafka decouples ingestion latency from storage latency. The ingestion API returns 202 in <5ms regardless of DB state.

## Why batch inserts?

Single-row inserts at high throughput create WAL pressure and index update overhead. Batch inserts (100 rows per `executemany`) reduce round-trips by 100x and allow PostgreSQL to optimize index updates.

## Why Dead Letter Queue?

Without DLQ, a malformed message blocks the consumer forever (or gets skipped silently). DLQ lets you replay failed messages after fixing the parser, with full auditability.

## Why asyncpg over SQLAlchemy?

asyncpg is a native async PostgreSQL driver — no sync/async bridge, no ORM overhead. For a read-heavy query API, raw SQL with asyncpg gives 3-5x lower latency than SQLAlchemy async.

## Why Redis for rate limiting?

In-memory rate limiting breaks with multiple workers (each process has its own counter). Redis sorted sets give atomic, distributed sliding windows with O(log N) operations.

## Why PostgreSQL full-text search instead of Elasticsearch?

For a system at <10M logs/day, PostgreSQL GIN indexes on `tsvector` give sub-10ms full-text queries without the operational complexity of an Elasticsearch cluster.
