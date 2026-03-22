"""LogForge alerting service.

Runs as a background job. Every 60 seconds:
1. Reads all enabled alert rules from PostgreSQL
2. Counts matching log events within each rule's window
3. If threshold exceeded, writes an alert_event record
4. Logs the alert (webhook/Slack delivery can be added)

This is what separates a real observability system from a log viewer.
"""
from __future__ import annotations
import asyncio
import logging
import signal
from datetime import UTC, datetime, timedelta

import asyncpg

from common.settings import DatabaseSettings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

db_settings = DatabaseSettings()
CHECK_INTERVAL = 60  # seconds


async def check_rules(conn: asyncpg.Connection) -> None:
    rules = await conn.fetch(
        "SELECT id, service_name, level, threshold, window_seconds FROM alert_rules WHERE enabled = TRUE"
    )

    for rule in rules:
        window_start = datetime.now(UTC) - timedelta(seconds=rule["window_seconds"])

        if rule["service_name"]:
            count = await conn.fetchval(
                """SELECT COUNT(*) FROM logs
                   WHERE level = $1 AND service_name = $2 AND timestamp >= $3""",
                rule["level"], rule["service_name"], window_start,
            )
            service_label = rule["service_name"]
        else:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM logs WHERE level = $1 AND timestamp >= $2",
                rule["level"], window_start,
            )
            service_label = "*"

        if count >= rule["threshold"]:
            # Check if we already fired this alert in the last window (dedup)
            existing = await conn.fetchval(
                """SELECT id FROM alert_events
                   WHERE rule_id = $1 AND window_start >= $2 AND acknowledged = FALSE""",
                rule["id"], window_start,
            )
            if existing:
                continue

            await conn.execute(
                """INSERT INTO alert_events
                   (rule_id, service_name, level, count, window_start, window_end)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                rule["id"], service_label, rule["level"],
                count, window_start, datetime.now(UTC),
            )
            logger.warning(
                "ALERT FIRED | service=%s level=%s count=%d threshold=%d window=%ds",
                service_label, rule["level"], count, rule["threshold"], rule["window_seconds"],
            )


async def run_alerting() -> None:
    pool = await asyncpg.create_pool(db_settings.database_url, min_size=1, max_size=3)
    running = True

    def shutdown(sig, frame):
        nonlocal running
        logger.info("Alerting service shutting down")
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logger.info("Alerting service started — checking every %ds", CHECK_INTERVAL)

    while running:
        try:
            async with pool.acquire() as conn:
                await check_rules(conn)
        except Exception:
            logger.exception("Alert check failed")
        await asyncio.sleep(CHECK_INTERVAL)

    await pool.close()
    logger.info("Alerting service stopped")


if __name__ == "__main__":
    asyncio.run(run_alerting())
