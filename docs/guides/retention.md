# Data Retention

## Default Retention

By default, logforge retains all logs indefinitely. Configure retention policies to control storage costs.

## Policy Configuration

```sql
-- Set 30-day retention for all logs
INSERT INTO retention_policies (service, level, retain_days)
VALUES ('*', '*', 30);

-- Keep ERROR logs for 90 days
INSERT INTO retention_policies (service, level, retain_days)
VALUES ('*', 'ERROR', 90);

-- Audit logs: 1 year
INSERT INTO retention_policies (service, level, retain_days)
VALUES ('audit-service', '*', 365);
```

## Automatic Cleanup

A background job runs nightly at 02:00 UTC to delete expired logs:

```bash
# Manual trigger
curl -X POST http://localhost:8002/admin/cleanup

# Response
{"deleted": 1234567, "freed_mb": 4567, "duration_seconds": 12.3}
```

## Archival (S3)

Before deletion, logs can be archived to S3:

```yaml
# config/retention.yml
archival:
  enabled: true
  bucket: s3://my-logs-archive/
  format: parquet
  compress: gzip
```

## Storage Estimates

| Retention | 1M logs/day | 10M logs/day |
|---|---|---|
| 7 days | ~7GB | ~70GB |
| 30 days | ~30GB | ~300GB |
| 90 days | ~90GB | ~900GB |

Assumes ~1KB average log size after JSONB compression.
