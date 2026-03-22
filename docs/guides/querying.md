# Query API Guide

## Full-Text Search

```bash
GET /logs/search?q=timeout&limit=100&offset=0
```

Response:

```json
{
  "total": 42,
  "logs": [
    {
      "id": "...",
      "service": "api-gateway",
      "level": "ERROR",
      "message": "Connection timeout to database",
      "timestamp": "2024-01-15T10:23:45Z",
      "metadata": {"host": "web-01"}
    }
  ]
}
```

## Filter by Service and Level

```bash
GET /logs/search?service=api-gateway&level=ERROR&start=2024-01-15T00:00:00Z
```

## Aggregations

```bash
GET /logs/aggregate?group_by=service&metric=count&window=1h
```

Response:

```json
{
  "window": "1h",
  "buckets": [
    {"service": "api-gateway", "count": 15234, "error_count": 42},
    {"service": "worker", "count": 8901, "error_count": 3}
  ]
}
```

## Caching

Queries are cached in Redis with a 60-second TTL. Cache-bust with:

```bash
GET /logs/search?q=error&cache=false
```
