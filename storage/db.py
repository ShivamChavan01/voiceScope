import os
import asyncpg
from typing import Optional
from utils.logger import logger

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> Optional[asyncpg.Pool]:
    global _pool
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return None
    if _pool is None or _pool._closed:
        _pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("[DB] PostgreSQL pool connected")
    return _pool


async def close_pool():
    global _pool
    if _pool and not _pool._closed:
        await _pool.close()
        _pool = None
        logger.info("[DB] PostgreSQL pool closed")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cost_logs (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS runs (
    id SERIAL PRIMARY KEY,
    run_id TEXT UNIQUE NOT NULL,
    intent TEXT,
    sentiment TEXT,
    outcome TEXT,
    hallucination_detected INTEGER DEFAULT 0,
    escalation_signal INTEGER DEFAULT 0,
    truth_score DOUBLE PRECISION,
    confidence TEXT,
    quality_score DOUBLE PRECISION,
    cost_usd DOUBLE PRECISION DEFAULT 0.0,
    provider TEXT,
    model TEXT,
    duration_seconds DOUBLE PRECISION,
    word_count INTEGER,
    transcript_preview TEXT,
    transcript_speakers JSONB,
    layer_scores JSONB,
    status TEXT DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS call_metrics (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    platform TEXT,
    intent TEXT,
    sentiment_arc TEXT,
    outcome TEXT,
    hallucination_detected INTEGER DEFAULT 0,
    escalation_signal INTEGER DEFAULT 0,
    quality_score DOUBLE PRECISION,
    cost_usd DOUBLE PRECISION DEFAULT 0.0,
    duration_seconds DOUBLE PRECISION,
    word_count INTEGER,
    provider TEXT,
    model TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alert_rules (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    metric TEXT NOT NULL,
    comparator TEXT NOT NULL,
    threshold DOUBLE PRECISION NOT NULL,
    window_minutes INTEGER DEFAULT 60,
    enabled INTEGER DEFAULT 1,
    notify_url TEXT,
    notify_email TEXT,
    last_triggered TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alert_incidents (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES alert_rules(id),
    metric_value DOUBLE PRECISION,
    message TEXT,
    status TEXT DEFAULT 'active',
    triggered_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_run_id ON runs(run_id);
CREATE INDEX IF NOT EXISTS idx_call_metrics_created_at ON call_metrics(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cost_logs_created_at ON cost_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_incidents_triggered_at ON alert_incidents(triggered_at DESC);
"""


async def init_schema():
    pool = await get_pool()
    if pool is None:
        return
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    logger.info("[DB] PostgreSQL schema initialized")
