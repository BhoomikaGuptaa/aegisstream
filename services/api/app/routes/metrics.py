"""Metrics API routes."""
from __future__ import annotations

import sys
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared")

from fastapi import APIRouter, Query
from services.api.app.database import get_conn

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/overview")
def get_overview():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0]
        evaluated = conn.execute("SELECT COUNT(*) FROM evaluated_events").fetchone()[0]
        reviews = conn.execute("SELECT COUNT(*) FROM review_queue").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM review_queue WHERE review_status='pending'").fetchone()[0]
        blocking = conn.execute("SELECT COUNT(*) FROM evaluated_events WHERE deployment_blocking=1").fetchone()[0]

        scores = conn.execute("""
            SELECT AVG(risk_score), AVG(reliability_score), AVG(safety_score),
                   AVG(groundedness_score), AVG(usefulness_score)
            FROM evaluated_events
        """).fetchone()

        latency = conn.execute("""
            SELECT AVG(latency_ms), MAX(latency_ms), MIN(latency_ms)
            FROM raw_events
        """).fetchone()

        cost = conn.execute("""
            SELECT SUM(estimated_cost_usd), AVG(estimated_cost_usd)
            FROM raw_events
        """).fetchone()

    return {
        "total_events": total,
        "evaluated_events": evaluated,
        "review_queue_total": reviews,
        "review_queue_pending": pending,
        "deployment_blocking_events": blocking,
        "review_rate": round(reviews / max(1, total) * 100, 2),
        "avg_risk_score": round(scores[0] or 0, 2),
        "avg_reliability_score": round(scores[1] or 0, 2),
        "avg_safety_score": round(scores[2] or 0, 2),
        "avg_groundedness_score": round(scores[3] or 0, 2),
        "avg_usefulness_score": round(scores[4] or 0, 2),
        "avg_latency_ms": round(latency[0] or 0, 2),
        "max_latency_ms": round(latency[1] or 0, 2),
        "total_cost_usd": round(cost[0] or 0, 6),
        "avg_cost_usd": round(cost[1] or 0, 8),
    }


@router.get("/timeseries")
def get_timeseries(minutes: int = Query(60, ge=5, le=1440)):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                strftime('%Y-%m-%dT%H:%M:00', r.timestamp) as bucket,
                COUNT(*) as event_count,
                AVG(e.risk_score) as avg_risk,
                AVG(e.reliability_score) as avg_reliability,
                AVG(e.safety_score) as avg_safety,
                AVG(r.latency_ms) as avg_latency,
                SUM(CASE WHEN e.review_required=1 THEN 1 ELSE 0 END) as reviews
            FROM raw_events r
            LEFT JOIN evaluated_events e ON r.event_id = e.event_id
            WHERE r.timestamp >= datetime('now', ?)
            GROUP BY bucket
            ORDER BY bucket
        """, (f"-{minutes} minutes",)).fetchall()
    return [dict(r) for r in rows]


@router.get("/risk-distribution")
def get_risk_distribution():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                CASE
                    WHEN risk_score < 20 THEN '0-20 (Low)'
                    WHEN risk_score < 40 THEN '20-40 (Moderate)'
                    WHEN risk_score < 60 THEN '40-60 (High)'
                    WHEN risk_score < 80 THEN '60-80 (Critical)'
                    ELSE '80-100 (Severe)'
                END as bucket,
                COUNT(*) as count
            FROM evaluated_events
            GROUP BY bucket
            ORDER BY bucket
        """).fetchall()
    return [dict(r) for r in rows]


@router.get("/model-comparison")
def get_model_comparison():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                r.model_name,
                r.provider,
                COUNT(*) as total_events,
                AVG(e.risk_score) as avg_risk,
                AVG(e.reliability_score) as avg_reliability,
                AVG(e.safety_score) as avg_safety,
                AVG(e.groundedness_score) as avg_groundedness,
                AVG(r.latency_ms) as avg_latency_ms,
                AVG(r.estimated_cost_usd) as avg_cost,
                SUM(CASE WHEN e.review_required=1 THEN 1 ELSE 0 END)*100.0/COUNT(*) as review_rate,
                SUM(CASE WHEN e.deployment_blocking=1 THEN 1 ELSE 0 END)*100.0/COUNT(*) as blocking_rate
            FROM raw_events r
            LEFT JOIN evaluated_events e ON r.event_id = e.event_id
            GROUP BY r.model_name
            ORDER BY avg_risk ASC
        """).fetchall()
    return [dict(r) for r in rows]


@router.get("/route-comparison")
def get_route_comparison():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                r.route_name,
                COUNT(*) as total_events,
                AVG(e.risk_score) as avg_risk,
                AVG(e.reliability_score) as avg_reliability,
                AVG(r.latency_ms) as avg_latency_ms,
                SUM(CASE WHEN e.review_required=1 THEN 1 ELSE 0 END)*100.0/COUNT(*) as review_rate
            FROM raw_events r
            LEFT JOIN evaluated_events e ON r.event_id = e.event_id
            GROUP BY r.route_name
            ORDER BY avg_risk DESC
        """).fetchall()
    return [dict(r) for r in rows]


@router.get("/failure-modes")
def get_failure_modes(limit: int = Query(15, ge=5, le=50)):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT label, COUNT(*) as count,
                   AVG(score_delta) as avg_delta,
                   MAX(severity) as max_severity
            FROM evaluator_results
            WHERE passed=0
            GROUP BY label
            ORDER BY count DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


@router.get("/drift")
def get_drift_alerts(limit: int = Query(20, ge=1, le=100)):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM drift_alerts ORDER BY detected_at DESC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


@router.get("/latency-percentiles")
def get_latency_percentiles():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT latency_ms FROM raw_events ORDER BY latency_ms
        """).fetchall()
    if not rows:
        return {"p50": 0, "p95": 0, "p99": 0, "avg": 0}
    latencies = sorted(r[0] for r in rows)
    n = len(latencies)
    return {
        "p50": round(latencies[int(n * 0.50)], 2),
        "p95": round(latencies[int(n * 0.95)], 2),
        "p99": round(latencies[min(int(n * 0.99), n - 1)], 2),
        "avg": round(sum(latencies) / n, 2),
        "count": n,
    }
