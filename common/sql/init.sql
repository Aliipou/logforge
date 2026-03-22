-- LogForge database schema
-- Run automatically via docker-entrypoint-initdb.d

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS logs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    service_name TEXT NOT NULL,
    level        TEXT NOT NULL CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    message      TEXT NOT NULL,
    metadata     JSONB NOT NULL DEFAULT '{}'
);

-- Core access patterns
CREATE INDEX idx_logs_timestamp     ON logs(timestamp DESC);
CREATE INDEX idx_logs_service       ON logs(service_name);
CREATE INDEX idx_logs_level         ON logs(level);
CREATE INDEX idx_logs_service_ts    ON logs(service_name, timestamp DESC);
CREATE INDEX idx_logs_level_ts      ON logs(level, timestamp DESC);

-- Full-text search
CREATE INDEX idx_logs_fts           ON logs USING gin(to_tsvector('english', message));

-- JSONB metadata queries
CREATE INDEX idx_logs_metadata      ON logs USING gin(metadata);

-- Alert rules
CREATE TABLE IF NOT EXISTS alert_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name    TEXT,               -- NULL = applies to all services
    level           TEXT NOT NULL DEFAULT 'ERROR',
    threshold       INTEGER NOT NULL,   -- events per window
    window_seconds  INTEGER NOT NULL DEFAULT 60,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alert_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id         UUID NOT NULL REFERENCES alert_rules(id),
    service_name    TEXT NOT NULL,
    level           TEXT NOT NULL,
    count           INTEGER NOT NULL,
    window_start    TIMESTAMPTZ NOT NULL,
    window_end      TIMESTAMPTZ NOT NULL,
    acknowledged    BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alert_events_rule      ON alert_events(rule_id);
CREATE INDEX idx_alert_events_active    ON alert_events(acknowledged, created_at DESC);

-- Insert default alert rule
INSERT INTO alert_rules (service_name, level, threshold, window_seconds)
VALUES (NULL, 'ERROR', 50, 60)
ON CONFLICT DO NOTHING;
