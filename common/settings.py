"""Shared settings across all LogForge services."""
from __future__ import annotations
from pydantic_settings import BaseSettings


class KafkaSettings(BaseSettings):
    model_config = {"env_prefix": "KAFKA_", "case_sensitive": False}
    bootstrap_servers: str = "localhost:9092"
    topic: str = "logs-topic"
    dlq_topic: str = "logs-topic-dlq"
    group_id: str = "logforge-processor"


class DatabaseSettings(BaseSettings):
    model_config = {"env_prefix": "", "case_sensitive": False}
    database_url: str = "postgresql://logforge:logforge_dev@localhost:5432/logforge"


class RedisSettings(BaseSettings):
    model_config = {"env_prefix": "", "case_sensitive": False}
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_per_minute: int = 100
