"""Reviews and deployment gate API routes."""
from __future__ import annotations

import json
import sys
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared")

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.api.app.database import get_conn
from shared.schemas import DeploymentCheckRequest, DeploymentCheckResult

reviews_router = APIRouter(prefix="/reviews", tags=["reviews"])
deployment_router = APIRouter(prefix="/deployment", tags=["deployment"])


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

class ReviewPatch(BaseModel):
    review_status: str  # approved | rejected | escalated
    reviewer_notes: Optional[str] = None


@reviews_router.get("/")
def list_reviews(
    status: str = Query("pending"),
    limit: int = Query(50, ge=1, le=200),
):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT rq.*, r.model_name, r.route_name, r.prompt, r.response,
                   e.safety_score, e.risk_score
            FROM review_queue rq
            LEFT JOIN raw_events r ON rq.event_id = r.event_id
            LEFT JOIN evaluated_events e ON rq.event_id = e.event_id
            WHERE rq.review_status = ?
            ORDER BY rq.risk_score DESC
            LIMIT ?
        """, (status, limit)).fetchall()
    return [dict(r) for r in rows]


@reviews_router.patch("/{event_id}")
def update_review(event_id: str, patch: ReviewPatch):
    valid = {"approved", "rejected", "escalated", "pending"}
    if patch.review_status not in valid:
        raise HTTPException(400, f"status must be one of {valid}")

    with get_conn() as conn:
        row = conn.execute(
            "SELECT event_id FROM review_queue WHERE event_id=?", (event_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Review not found")
        conn.execute("""
            UPDATE review_queue
            SET review_status=?, reviewer_notes=?, reviewed_at=?
            WHERE event_id=?
        """, (patch.review_status, patch.reviewer_notes,
              datetime.utcnow().isoformat(), event_id))
        conn.commit()
    return {"event_id": event_id, "status": patch.review_status}


# ---------------------------------------------------------------------------
# Deployment gate
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS = {
    "max_review_rate": 15.0,
    "max_avg_risk_score": 35.0,
    "max_p95_latency_ms": 3000.0,
    "max_injection_rate": 5.0,
    "max_sensitive_data_rate": 3.0,
    "max_hallucination_rate": 10.0,
    "min_reliability_score": 70.0,
}


@deployment_router.get("/readiness")
def get_readiness(window_minutes: int = Query(60)):
    return _run_check("all", "all", "production", window_minutes, DEFAULT_THRESHOLDS)


@deployment_router.post("/check")
def run_deployment_check(req: DeploymentCheckRequest):
    thresholds = {**DEFAULT_THRESHOLDS, **(req.thresholds or {})}
    return _run_check(req.model_name, req.route_name, req.environment,
                      req.window_minutes, thresholds)


def _run_check(model_name, route_name, environment, window_minutes, thresholds):
    with get_conn() as conn:
        where_clauses = [f"r.timestamp >= datetime('now', '-{window_minutes} minutes')"]
        params = []
        if model_name != "all":
            where_clauses.append("r.model_name = ?")
            params.append(model_name)
        if route_name != "all":
            where_clauses.append("r.route_name = ?")
            params.append(route_name)

        where_sql = " AND ".join(where_clauses)

        stats = conn.execute(f"""
            SELECT
                COUNT(*) as total,
                AVG(e.risk_score) as avg_risk,
                AVG(e.reliability_score) as avg_reliability,
                SUM(CASE WHEN e.review_required=1 THEN 1.0 ELSE 0 END)/COUNT(*)*100 as review_rate,
                AVG(r.latency_ms) as avg_latency
            FROM raw_events r
            LEFT JOIN evaluated_events e ON r.event_id = e.event_id
            WHERE {where_sql}
        """, params).fetchone()

        # Label-specific rates
        def label_rate(label):
            count = conn.execute(f"""
                SELECT COUNT(DISTINCT er.event_id)
                FROM evaluator_results er
                JOIN raw_events r ON er.event_id = r.event_id
                WHERE er.label=? AND {where_sql}
            """, [label] + params).fetchone()[0]
            total = max(1, stats[0] or 1)
            return count / total * 100

        injection_rate = label_rate("prompt_injection")
        sensitive_rate = label_rate("pii_in_prompt") + label_rate("payment_card_in_prompt")
        halluc_rate = label_rate("hallucination_detected")

        latency_rows = conn.execute(f"""
            SELECT latency_ms FROM raw_events r WHERE {where_sql} ORDER BY latency_ms
        """, params).fetchall()

    latencies = sorted(r[0] for r in latency_rows)
    n = len(latencies)
    p95 = latencies[int(n * 0.95)] if n > 0 else 0

    metrics = {
        "total_events": stats[0] or 0,
        "avg_risk_score": round(stats[1] or 0, 2),
        "avg_reliability_score": round(stats[2] or 0, 2),
        "review_rate": round(stats[3] or 0, 2),
        "p95_latency_ms": round(p95, 2),
        "injection_rate": round(injection_rate, 2),
        "sensitive_data_rate": round(sensitive_rate, 2),
        "hallucination_rate": round(halluc_rate, 2),
    }

    failures = []
    warnings = []

    checks = [
        ("review_rate", metrics["review_rate"], thresholds["max_review_rate"], ">"),
        ("avg_risk_score", metrics["avg_risk_score"], thresholds["max_avg_risk_score"], ">"),
        ("p95_latency_ms", metrics["p95_latency_ms"], thresholds["max_p95_latency_ms"], ">"),
        ("injection_rate", metrics["injection_rate"], thresholds["max_injection_rate"], ">"),
        ("sensitive_data_rate", metrics["sensitive_data_rate"], thresholds["max_sensitive_data_rate"], ">"),
        ("hallucination_rate", metrics["hallucination_rate"], thresholds["max_hallucination_rate"], ">"),
        ("avg_reliability_score", metrics["avg_reliability_score"], thresholds["min_reliability_score"], "<"),
    ]

    for name, value, threshold, op in checks:
        if op == ">" and value > threshold:
            failures.append(f"{name}={value:.2f} exceeds threshold {threshold}")
        elif op == "<" and value < threshold:
            failures.append(f"{name}={value:.2f} below threshold {threshold}")

    passed = len(failures) == 0
    recommendation = (
        "APPROVED: All metrics within thresholds." if passed
        else f"BLOCKED: {len(failures)} threshold(s) violated. Review before deploying."
    )

    return DeploymentCheckResult(
        passed=passed,
        model_name=model_name,
        route_name=route_name,
        environment=environment,
        metrics=metrics,
        thresholds=thresholds,
        failures=failures,
        warnings=warnings,
        recommendation=recommendation,
    )
