# Alerting Guide

## Alert Rules

Create rules via the API:

```bash
POST /alerts/rules
Content-Type: application/json

{
  "service": "api-gateway",
  "level": "ERROR",
  "threshold": 10,
  "window_minutes": 5,
  "channel": "slack",
  "webhook_url": "https://hooks.slack.com/services/..."
}
```

This fires a Slack alert if api-gateway logs more than 10 ERROR entries in any 5-minute window.

## Alert Payload

```json
{
  "alert": "HIGH_ERROR_RATE",
  "service": "api-gateway",
  "level": "ERROR",
  "count": 15,
  "threshold": 10,
  "window_minutes": 5,
  "triggered_at": "2024-01-15T10:23:45Z",
  "sample_logs": [...]
}
```

## Supported Channels

- `slack` — Webhook URL required
- `webhook` — Generic HTTP POST

## Alert History

```bash
GET /alerts/events?service=api-gateway&limit=50
```
