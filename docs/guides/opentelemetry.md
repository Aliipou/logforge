# OpenTelemetry Integration

Export metrics to OTel collector:

```yaml
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    ports:
      - "4317:4317"
```
