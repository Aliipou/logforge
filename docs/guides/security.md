# Security Guide

## Authentication

logforge uses API key authentication for all endpoints:

```bash
# Include in all requests
curl -H "X-API-Key: your-key" http://localhost:8002/logs/search?q=error
```

## API Key Management

```bash
# Create key
POST /admin/api-keys
{"name": "ingestion-service", "permissions": ["write"]}

# List keys
GET /admin/api-keys

# Revoke key
DELETE /admin/api-keys/{key-id}
```

## TLS

Enable TLS termination in the reverse proxy (nginx/Traefik). Never expose logforge directly to the internet.

## Network Isolation

Recommended network topology:

```
Internet → Nginx (TLS) → logforge ingestion (port 8001)
Internal → logforge query (port 8002) [internal only]
Internal → logforge admin (port 8003) [admin subnet only]
```

## Audit Trail

All administrative actions (key creation, retention policy changes) are logged to a separate, append-only audit table.

## PII Redaction

Enable automatic PII redaction in the ingestion service:

```yaml
# config/redaction.yml
redact_fields:
  - email
  - password
  - token
  - credit_card
patterns:
  - "\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"
```
