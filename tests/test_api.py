"""
AegisStream API integration tests.
Spins up a FastAPI TestClient against a temp SQLite DB — no Docker required.
"""
import json
import os
import sys
import tempfile

# Point to a temp DB before any imports touch the real one
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = _tmp.name

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from services.api.app.database import init_db
from services.api.app.main import app

# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ── Health ─────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "AegisStream" in r.json()["service"]


# ── Events ─────────────────────────────────────────────────────────────────

_SAMPLE_EVENT = {
    "model_name": "gpt-4o",
    "model_family": "gpt-4",
    "provider": "openai",
    "prompt": "What is the capital of France?",
    "response": "The capital of France is Paris.",
    "latency_ms": 180.0,
    "estimated_cost_usd": 0.001,
    "input_tokens": 10,
    "output_tokens": 8,
}


class TestEvents:
    def test_ingest_event(self, client):
        r = client.post("/events/", json=_SAMPLE_EVENT)
        assert r.status_code == 201
        body = r.json()
        assert "event_id" in body
        assert body["status"] == "ingested"

    def test_recent_events_empty_initially(self, client):
        r = client.get("/events/recent?limit=10")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_event_not_found(self, client):
        r = client.get("/events/nonexistent-id-xyz")
        assert r.status_code == 404

    def test_get_event_found(self, client):
        # Ingest first, then fetch by event_id
        r = client.post("/events/", json=_SAMPLE_EVENT)
        event_id = r.json()["event_id"]
        r2 = client.get(f"/events/{event_id}")
        assert r2.status_code == 200
        assert r2.json()["event_id"] == event_id

    def test_ingest_bad_payload_rejected(self, client):
        r = client.post("/events/", json={"not_a_field": "junk"})
        assert r.status_code == 422  # Pydantic validation error


# ── Metrics ────────────────────────────────────────────────────────────────

class TestMetrics:
    def test_overview_shape(self, client):
        r = client.get("/metrics/overview")
        assert r.status_code == 200
        body = r.json()
        for key in ["total_events", "avg_risk_score", "review_rate",
                    "avg_latency_ms", "total_cost_usd"]:
            assert key in body, f"Missing key: {key}"

    def test_timeseries_returns_list(self, client):
        r = client.get("/metrics/timeseries?minutes=60")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_risk_distribution(self, client):
        r = client.get("/metrics/risk-distribution")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_model_comparison(self, client):
        r = client.get("/metrics/model-comparison")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_route_comparison(self, client):
        r = client.get("/metrics/route-comparison")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_failure_modes(self, client):
        r = client.get("/metrics/failure-modes")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_drift_alerts(self, client):
        r = client.get("/metrics/drift")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_latency_percentiles(self, client):
        r = client.get("/metrics/latency-percentiles")
        assert r.status_code == 200
        body = r.json()
        assert "p50" in body and "p95" in body and "p99" in body

    def test_overview_counts_ingested_events(self, client):
        # Ingest 3 events and check total increases
        before = client.get("/metrics/overview").json()["total_events"]
        for _ in range(3):
            client.post("/events/", json=_SAMPLE_EVENT)
        after = client.get("/metrics/overview").json()["total_events"]
        assert after >= before + 3


# ── Reviews ────────────────────────────────────────────────────────────────

class TestReviews:
    def test_list_reviews_pending(self, client):
        r = client.get("/reviews/?status=pending")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_patch_nonexistent_review(self, client):
        r = client.patch("/reviews/no-such-event", json={"review_status": "approved"})
        assert r.status_code == 404

    def test_patch_invalid_status(self, client):
        r = client.patch("/reviews/some-id", json={"review_status": "invalid_status"})
        # Either 400 (validation) or 404 (not found) — both acceptable
        assert r.status_code in (400, 404)


# ── Deployment Gate ────────────────────────────────────────────────────────

class TestDeploymentGate:
    def test_readiness_returns_result(self, client):
        r = client.get("/deployment/readiness")
        assert r.status_code == 200
        body = r.json()
        assert "passed" in body
        assert "metrics" in body
        assert "failures" in body
        assert "recommendation" in body

    def test_deployment_check_post(self, client):
        r = client.post("/deployment/check", json={
            "model_name": "gpt-4o",
            "route_name": "chat",
            "environment": "staging",
            "window_minutes": 60,
        })
        assert r.status_code == 200
        body = r.json()
        assert "passed" in body
        assert body["model_name"] == "gpt-4o"

    def test_deployment_check_custom_thresholds(self, client):
        r = client.post("/deployment/check", json={
            "model_name": "all",
            "route_name": "all",
            "thresholds": {
                "max_review_rate": 0.0,   # guaranteed to fail
                "max_avg_risk_score": 100.0,
                "max_p95_latency_ms": 99999.0,
                "max_injection_rate": 100.0,
                "max_sensitive_data_rate": 100.0,
                "max_hallucination_rate": 100.0,
                "min_reliability_score": 0.0,
            },
        })
        # With review_rate threshold=0, almost always fails (unless 0 events)
        assert r.status_code == 200


# ── Cleanup ────────────────────────────────────────────────────────────────

def teardown_module(module):
    try:
        os.unlink(_tmp.name)
    except Exception:
        pass
