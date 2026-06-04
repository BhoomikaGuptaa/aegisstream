"""
AegisStream evaluator consumer.
Reads from aegis.raw_events, runs all evaluators, persists to DB,
publishes to evaluated/review/drift topics.
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/app")

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

from services.evaluator.app.evaluators import ALL_EVALUATORS
from services.evaluator.app.scoring import compute_scores
from shared.kafka import (
    KAFKA_BOOTSTRAP, TOPIC_DRIFT_ALERTS, TOPIC_EVALUATED_EVENTS,
    TOPIC_RAW_EVENTS, TOPIC_REVIEW_EVENTS, deserialize, serialize,
)
from shared.schemas import DriftAlert, LLMEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [EVALUATOR] %(message)s")
log = logging.getLogger(__name__)

# In-process drift tracking (rolling window counters)
_window_size = 100
_recent_scores: list = []
_baseline_risk: float = 15.0  # expected baseline


def wait_for_kafka(retries=15, delay=4.0):
    for i in range(retries):
        try:
            consumer = KafkaConsumer(
                TOPIC_RAW_EVENTS,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id="aegis-evaluator",
                auto_offset_reset="latest",
                value_deserializer=lambda v: deserialize(v),
            )
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: serialize(v),
            )
            log.info("Connected to Kafka.")
            return consumer, producer
        except NoBrokersAvailable:
            log.warning("Kafka not ready (%d/%d)...", i + 1, retries)
            time.sleep(delay)
    raise RuntimeError("Kafka unavailable.")


def check_drift(evaluated, producer) -> None:
    global _recent_scores
    _recent_scores.append(evaluated.risk_score)
    if len(_recent_scores) > _window_size:
        _recent_scores = _recent_scores[-_window_size:]

    if len(_recent_scores) < 20:
        return

    rolling_avg = sum(_recent_scores) / len(_recent_scores)
    if rolling_avg > _baseline_risk * 2.5:
        alert = DriftAlert(
            alert_type="risk_score_spike",
            severity="high" if rolling_avg > _baseline_risk * 4 else "medium",
            model_name=evaluated.event.model_name,
            route_name=evaluated.event.route_name,
            metric_name="avg_risk_score",
            current_value=rolling_avg,
            baseline_value=_baseline_risk,
            threshold=_baseline_risk * 2.5,
            message=f"Rolling avg risk score {rolling_avg:.1f} exceeds 2.5x baseline ({_baseline_risk}).",
        )
        producer.send(TOPIC_DRIFT_ALERTS, value=alert)
        log.warning("DRIFT ALERT: %s", alert.message)


def run():
    # Import here to avoid circular DB init at module level
    import sqlite3
    import os

    db_path = os.getenv("DATABASE_URL", "/data/aegisstream.db").replace("sqlite:///", "")

    consumer, producer = wait_for_kafka()
    log.info("Evaluator started. Consuming from %s", TOPIC_RAW_EVENTS)
    count = 0

    for message in consumer:
        try:
            raw = message.value
            event = LLMEvent(**raw)

            # Run all evaluators
            results = [ev.evaluate(event) for ev in ALL_EVALUATORS]
            evaluated = compute_scores(event, results)

            # Publish to evaluated topic
            producer.send(TOPIC_EVALUATED_EVENTS, value=evaluated)

            # Publish to review queue if flagged
            if evaluated.review_required:
                producer.send(TOPIC_REVIEW_EVENTS, value=evaluated)

            # Persist to SQLite
            _persist(db_path, evaluated)

            # Drift detection
            check_drift(evaluated, producer)

            count += 1
            if count % 50 == 0:
                log.info("Evaluated %d events | last risk=%.1f | review=%s",
                         count, evaluated.risk_score, evaluated.review_required)

        except Exception as e:
            log.error("Evaluation error: %s", e, exc_info=True)


def _persist(db_path: str, evaluated) -> None:
    """Write evaluated event to SQLite."""
    import sqlite3, json
    with sqlite3.connect(db_path) as conn:
        event = evaluated.event
        conn.execute("""
            INSERT OR REPLACE INTO raw_events VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
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
        conn.execute("""
            INSERT OR REPLACE INTO evaluated_events VALUES (
                ?,?,?,?,?,?,?,?,?,?
            )
        """, (
            event.event_id, evaluated.risk_score, evaluated.reliability_score,
            evaluated.usefulness_score, evaluated.safety_score,
            evaluated.groundedness_score, evaluated.review_required,
            evaluated.deployment_blocking, evaluated.primary_failure_mode,
            evaluated.evaluated_at.isoformat(),
        ))
        if evaluated.review_required:
            conn.execute("""
                INSERT OR IGNORE INTO review_queue VALUES (?,?,?,'pending',NULL,NULL)
            """, (event.event_id, evaluated.risk_score, evaluated.primary_failure_mode))

        for r in evaluated.evaluator_results:
            conn.execute("""
                INSERT INTO evaluator_results VALUES (
                    NULL,?,?,?,?,?,?,?,?,?
                )
            """, (
                event.event_id, r.evaluator_name, r.passed, r.severity,
                r.score_delta, r.label, r.explanation[:300], r.evidence[:200],
                r.confidence,
            ))
        conn.commit()


if __name__ == "__main__":
    run()
