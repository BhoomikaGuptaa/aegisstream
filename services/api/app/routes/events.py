"""Events API routes."""
from __future__ import annotations

import json
import logging
import os
import sys
sys.path.insert(0, "/app")

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from shared.schemas import LLMEvent
from services.api.app.database import get_conn

log = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["events"])

# ---------------------------------------------------------------------------
# Kafka producer (optional — gracefully disabled if Kafka is unreachable)
# ---------------------------------------------------------------------------
_kafka_producer = None

def _get_kafka_producer():
    """Lazy-init Kafka producer; returns None if Kafka is unavailable."""
    global _kafka_producer
    if _kafka_producer is not None:
        return _kafka_producer
    try:
        from kafka import KafkaProducer
        from shared.kafka import KAFKA_BOOTSTRAP, serialize, TOPIC_RAW_EVENTS
        _kafka_producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: serialize(v),
            request_timeout_ms=2000,
            retries=1,
        )
        log.info("API Kafka producer connected to %s", KAFKA_BOOTSTRAP)
        return _kafka_producer
    except Exception as e:
        log.warning("Kafka unavailable for API producer (%s); events will be evaluated inline.", e)
        return None


def _evaluate_and_persist(event: LLMEvent) -> None:
    """Run evaluators inline and persist — used when Kafka is not available."""
    from services.evaluator.app.evaluators import ALL_EVALUATORS
    from services.evaluator.app.scoring import compute_scores
    import sqlite3

    db_path = os.getenv("DATABASE_URL", "/data/aegisstream.db").replace("sqlite:///", "")
    results = [ev.evaluate(event) for ev in ALL_EVALUATORS]
    evaluated = compute_scores(event, results)

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO evaluated_events VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            event.event_id, evaluated.risk_score, evaluated.reliability_score,
            evaluated.usefulness_score, evaluated.safety_score,
            evaluated.groundedness_score, evaluated.review_required,
            evaluated.deployment_blocking, evaluated.primary_failure_mode,
            evaluated.evaluated_at.isoformat(),
        ))
        if evaluated.review_required:
            conn.execute(
                "INSERT OR IGNORE INTO review_queue VALUES (?,?,?,'pending',NULL,NULL)",
                (event.event_id, evaluated.risk_score, evaluated.primary_failure_mode),
            )
        for r in evaluated.evaluator_results:
            conn.execute(
                "INSERT INTO evaluator_results VALUES (NULL,?,?,?,?,?,?,?,?,?)",
                (event.event_id, r.evaluator_name, r.passed, r.severity,
                 r.score_delta, r.label, r.explanation[:300], r.evidence[:200], r.confidence),
            )
        conn.commit()


@router.post("/", status_code=201)
def ingest_event(event: LLMEvent):
    """
    Ingest a single LLM event.

    Behaviour:
    - Always writes to the raw_events table immediately.
    - If Kafka is reachable, publishes to aegis.raw_events so the evaluator
      service picks it up asynchronously (matching the streaming architecture).
    - If Kafka is not reachable (e.g. local dev without Docker), falls back to
      running all evaluators inline so the event still appears in metrics.
    """
    # 1. Persist raw event
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO raw_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            event.event_id, event.trace_id, event.session_id, event.user_id_hash,
            event.timestamp.isoformat(), event.app_name, event.route_name,
            event.environment, event.model_name, event.model_family, event.provider,
            event.prompt[:500], event.response[:1000],
            event.input_tokens, event.output_tokens, event.latency_ms,
            event.estimated_cost_usd, event.temperature,
            event.retrieved_context[:500] if event.retrieved_context else None,
            json.dumps(event.metadata),
        ))
        conn.commit()

    # 2. Try Kafka publish; fall back to inline evaluation
    producer = _get_kafka_producer()
    if producer:
        try:
            from shared.kafka import TOPIC_RAW_EVENTS
            producer.send(TOPIC_RAW_EVENTS, value=event)
            routed_via = "kafka"
        except Exception as e:
            log.warning("Kafka send failed (%s); falling back to inline evaluation.", e)
            _evaluate_and_persist(event)
            routed_via = "inline_fallback"
    else:
        _evaluate_and_persist(event)
        routed_via = "inline"

    return {"event_id": event.event_id, "status": "ingested", "routed_via": routed_via}


@router.get("/recent")
def get_recent_events(limit: int = Query(50, ge=1, le=500)):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT r.*, e.risk_score, e.reliability_score, e.review_required,
                   e.primary_failure_mode, e.safety_score
            FROM raw_events r
            LEFT JOIN evaluated_events e ON r.event_id = e.event_id
            ORDER BY r.timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


@router.get("/{event_id}")
def get_event(event_id: str):
    with get_conn() as conn:
        row = conn.execute("""
            SELECT r.*, e.risk_score, e.reliability_score, e.safety_score,
                   e.usefulness_score, e.groundedness_score,
                   e.review_required, e.deployment_blocking,
                   e.primary_failure_mode, e.evaluated_at
            FROM raw_events r
            LEFT JOIN evaluated_events e ON r.event_id = e.event_id
            WHERE r.event_id = ?
        """, (event_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Event not found")

        evals = conn.execute(
            "SELECT * FROM evaluator_results WHERE event_id = ?", (event_id,)
        ).fetchall()

    result = dict(row)
    result["evaluator_results"] = [dict(e) for e in evals]
    return result
