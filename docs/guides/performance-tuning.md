# Performance Tuning

## PostgreSQL Tuning

For a 4-core / 16GB server handling 1M logs/day:

```sql
-- postgresql.conf
shared_buffers = 4GB
effective_cache_size = 12GB
work_mem = 256MB
maintenance_work_mem = 1GB
max_connections = 100
checkpoint_completion_target = 0.9
wal_buffers = 64MB
random_page_cost = 1.1  -- for SSD
```

## Kafka Tuning

```properties
# Producer (ingestion_service)
batch.size=65536
linger.ms=10
compression.type=lz4
acks=1  # acceptable for logs (not financial data)

# Consumer (processor_service)
fetch.min.bytes=65536
fetch.max.wait.ms=500
max.poll.records=500
```

## Redis Tuning

```
# redis.conf
maxmemory 4gb
maxmemory-policy allkeys-lru
save ""  # disable snapshots (pure cache)
```

## Horizontal Scaling

- **Ingestion**: Stateless. Scale with: `docker compose scale ingestion=4`
- **Processor**: One partition = one consumer. Scale by adding Kafka partitions.
- **Query**: Read-only PostgreSQL replicas for heavy reporting queries.

## Connection Pool Settings

```python
# asyncpg pool tuning
pool = await asyncpg.create_pool(
    dsn,
    min_size=5,
    max_size=20,          # match max_connections/services
    command_timeout=30,
    max_inactive_connection_lifetime=300,
)
```
