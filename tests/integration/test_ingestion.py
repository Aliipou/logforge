"""Integration tests for the full ingestion → Kafka → processor → query flow.

Requires Docker (testcontainers spins up real Kafka and PostgreSQL).
Run with: pytest tests/integration -v
"""
import pytest

# These tests require testcontainers — skipped in unit-only runs
pytest.importorskip("testcontainers")

# Full integration tests would:
# 1. Start Kafka + PostgreSQL via testcontainers
# 2. POST to ingestion API
# 3. Run processor to consume from Kafka
# 4. Query the query API and assert the log appears
# 5. Assert alerting fires when threshold exceeded
#
# Stub here — full implementation in the next iteration.

# Placeholder removed � full integration tests will be added once testcontainers are wired up.
# See the scaffold comments above for the intended test flow.
