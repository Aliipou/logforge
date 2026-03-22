# Kafka Configuration

## Basic Setup

```yaml
# config/kafka.yml
bootstrap_servers: "kafka:9092"
topic: "logs"
dlq_topic: "logs-dlq"
consumer_group: "logforge-processor"
```

## Producer Configuration

```python
KAFKA_PRODUCER_CONFIG = {
    "bootstrap.servers": "kafka:9092",
    "acks": "1",              # balance between speed and durability
    "batch.size": 65536,      # 64KB batches
    "linger.ms": 10,          # wait up to 10ms to fill batch
    "compression.type": "lz4", # fast compression
    "retries": 3,
    "retry.backoff.ms": 100,
}
```

## Consumer Configuration

```python
KAFKA_CONSUMER_CONFIG = {
    "bootstrap.servers": "kafka:9092",
    "group.id": "logforge-processor",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,  # manual commit for exactly-once
    "max.poll.records": 500,
    "fetch.min.bytes": 65536,
    "fetch.max.wait.ms": 500,
}
```

## Scaling Partitions

```bash
# Increase partitions to scale consumers (one consumer per partition max)
kafka-topics --alter --topic logs \
  --partitions 8 \
  --bootstrap-server localhost:9092
```

Then scale processor instances:
```bash
docker compose scale processor=8
```

## Dead Letter Queue

Failed messages after 3 retries go to `logs-dlq`. Monitor and replay:

```bash
# View DLQ
kafka-console-consumer --topic logs-dlq --bootstrap-server kafka:9092 --from-beginning

# Replay DLQ to main topic (after fixing the issue)
kafka-console-consumer --topic logs-dlq | kafka-console-producer --topic logs --bootstrap-server kafka:9092
```
