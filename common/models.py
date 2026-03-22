"""Shared data models across LogForge services."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class LogEntry(BaseModel):
    """Incoming log payload (validated at ingestion)."""
    service_name: str = Field(..., min_length=1, max_length=128)
    level: str = Field(..., description="DEBUG | INFO | WARNING | ERROR | CRITICAL")
    message: str = Field(..., min_length=1, max_length=32768)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        v = v.upper()
        if v not in LOG_LEVELS:
            raise ValueError(f"level must be one of {sorted(LOG_LEVELS)}")
        return v

    @field_validator("service_name")
    @classmethod
    def validate_service_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("service_name must not be blank")
        return v


class StoredLog(LogEntry):
    """A log entry as stored in PostgreSQL."""
    id: UUID
    timestamp: datetime


class KafkaMessage(BaseModel):
    """Message envelope published to Kafka."""
    service_name: str
    level: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    ingested_at: str  # ISO 8601
