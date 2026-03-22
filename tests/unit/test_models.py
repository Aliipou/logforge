"""Unit tests for LogEntry validation."""
import pytest
from pydantic import ValidationError
from common.models import LogEntry


class TestLogEntry:
    def test_valid_entry(self):
        entry = LogEntry(service_name="auth", level="ERROR", message="token expired")
        assert entry.level == "ERROR"
        assert entry.service_name == "auth"

    def test_level_is_uppercased(self):
        entry = LogEntry(service_name="svc", level="error", message="msg")
        assert entry.level == "ERROR"

    def test_invalid_level_raises(self):
        with pytest.raises(ValidationError, match="level must be one of"):
            LogEntry(service_name="svc", level="VERBOSE", message="msg")

    def test_empty_service_name_raises(self):
        with pytest.raises(ValidationError):
            LogEntry(service_name="", level="INFO", message="msg")

    def test_metadata_defaults_to_empty_dict(self):
        entry = LogEntry(service_name="svc", level="INFO", message="ok")
        assert entry.metadata == {}

    def test_metadata_preserved(self):
        entry = LogEntry(service_name="svc", level="INFO", message="ok",
                        metadata={"user_id": 42, "ip": "1.2.3.4"})
        assert entry.metadata["user_id"] == 42

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    def test_all_valid_levels(self, level: str):
        entry = LogEntry(service_name="svc", level=level, message="test")
        assert entry.level == level
