"""
AegisStream database layer.
SQLite by default; schema initialization and query helpers.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

DATABASE_URL = os.getenv("DATABASE_URL", "/data/aegisstream.db")


def get_db_path() -> str:
    return DATABASE_URL.replace("sqlite:///", "")


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
    finally:
        conn.close()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS raw_events (
    event_id TEXT PRIMARY KEY,
    trace_id TEXT,
    session_id TEXT,
    user_id_hash TEXT,
    timestamp TEXT,
    app_name TEXT,
    route_name TEXT,
    environment TEXT,
    model_name TEXT,
    model_family TEXT,
    provider TEXT,
    prompt TEXT,
    response TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    latency_ms REAL,
    estimated_cost_usd REAL,
    temperature REAL,
    retrieved_context TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS evaluated_events (
    event_id TEXT PRIMARY KEY,
    risk_score REAL,
    reliability_score REAL,
    usefulness_score REAL,
    safety_score REAL,
    groundedness_score REAL,
    review_required INTEGER,
    deployment_blocking INTEGER,
    primary_failure_mode TEXT,
    evaluated_at TEXT
);

CREATE TABLE IF NOT EXISTS evaluator_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT,
    evaluator_name TEXT,
    passed INTEGER,
    severity TEXT,
    score_delta REAL,
    label TEXT,
    explanation TEXT,
    evidence TEXT,
    confidence REAL
);

CREATE TABLE IF NOT EXISTS review_queue (
    event_id TEXT PRIMARY KEY,
    risk_score REAL,
    primary_failure_mode TEXT,
    review_status TEXT DEFAULT 'pending',
    reviewer_notes TEXT,
    reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS drift_alerts (
    alert_id TEXT PRIMARY KEY,
    alert_type TEXT,
    severity TEXT,
    model_name TEXT,
    route_name TEXT,
    metric_name TEXT,
    current_value REAL,
    baseline_value REAL,
    threshold REAL,
    message TEXT,
    detected_at TEXT
);

CREATE TABLE IF NOT EXISTS deployment_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT,
    route_name TEXT,
    environment TEXT,
    passed INTEGER,
    metrics TEXT,
    failures TEXT,
    checked_at TEXT
);

CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_name TEXT,
    description TEXT,
    config TEXT,
    results TEXT,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_raw_events_model ON raw_events(model_name);
CREATE INDEX IF NOT EXISTS idx_raw_events_route ON raw_events(route_name);
CREATE INDEX IF NOT EXISTS idx_raw_events_ts ON raw_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_eval_risk ON evaluated_events(risk_score);
CREATE INDEX IF NOT EXISTS idx_review_status ON review_queue(review_status);
"""


def init_db() -> None:
    import os
    os.makedirs(os.path.dirname(get_db_path()) or ".", exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
