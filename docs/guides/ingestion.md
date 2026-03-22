# Log Ingestion Guide

## HTTP API

Send logs via HTTP:

```bash
curl -X POST http://localhost:8001/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "api-gateway",
    "level": "ERROR",
    "message": "Connection timeout",
    "metadata": {"host": "web-01", "request_id": "abc123"}
  }'
```

## Batch Ingestion

```bash
curl -X POST http://localhost:8001/ingest/batch \
  -H "Content-Type: application/json" \
  -d '{"logs": [...]}'
```

Rate limit: 10,000 requests/minute per IP (Redis sliding window).

## Kafka Producer (Direct)

```python
from confluent_kafka import Producer

producer = Producer({"bootstrap.servers": "localhost:9092"})

producer.produce(
    topic="logs",
    value=json.dumps({
        "service": "worker",
        "level": "INFO",
        "message": "Job completed",
        "metadata": {"job_id": "j-001", "records": 5000}
    }).encode()
)
producer.flush()
```

## Dead Letter Queue

Failed messages go to `logs-dlq` topic. Monitor with:

```bash
kafka-console-consumer --topic logs-dlq --bootstrap-server localhost:9092
```
