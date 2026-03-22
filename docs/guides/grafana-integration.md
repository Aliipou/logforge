# Grafana Integration

## Connecting LogForge to Grafana

LogForge exposes a JSON data source API compatible with Grafana Simple JSON plugin.

### Step 1: Install Plugin

```bash
grafana-cli plugins install grafana-simple-json-datasource
```

### Step 2: Add Data Source

1. In Grafana: Settings → Data Sources → Add data source
2. Type: Simple JSON
3. URL: `http://logforge:8002/grafana`

### Step 3: Create Dashboard

**Log Rate Panel:**
```json
{
  "target": "logs.rate.by_service",
  "filters": {"window": "1m"}
}
```

**Error Rate Panel:**
```json
{
  "target": "logs.error_rate",
  "filters": {"service": "api-gateway", "window": "5m"}
}
```

## Pre-built Dashboard

Import the bundled dashboard:

```bash
curl -X POST http://grafana:3000/api/dashboards/import \
  -H "Content-Type: application/json" \
  -d @dashboards/logforge-overview.json
```

## Alerting

Create Grafana alerts on LogForge metrics:

```
Error rate > 5% for 5 minutes → PagerDuty
Log volume drops > 50% → Slack
```
