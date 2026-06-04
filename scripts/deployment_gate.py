#!/usr/bin/env python3
"""
AegisStream Deployment Gate
==========================
Evaluates current streaming metrics against configurable thresholds.
Exits with code 0 on PASS, code 1 on FAIL.

Usage:
    python scripts/deployment_gate.py
    python scripts/deployment_gate.py --model gpt-4o --route rag_qa
    python scripts/deployment_gate.py --window 30 --max-risk 25
"""
import argparse
import json
import os
import sys
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "/data/aegisstream.db")

from services.api.app.database import get_db_path


def parse_args():
    p = argparse.ArgumentParser(description="AegisStream Deployment Gate")
    p.add_argument("--model",           default="all")
    p.add_argument("--route",           default="all")
    p.add_argument("--window",          type=int,   default=60,   help="Minutes to analyze")
    p.add_argument("--max-review-rate", type=float, default=15.0)
    p.add_argument("--max-risk",        type=float, default=35.0)
    p.add_argument("--max-p95-latency", type=float, default=3000.0)
    p.add_argument("--max-injection",   type=float, default=5.0)
    p.add_argument("--max-sensitive",   type=float, default=3.0)
    p.add_argument("--max-halluc",      type=float, default=10.0)
    p.add_argument("--min-reliability", type=float, default=70.0)
    p.add_argument("--json",            action="store_true", help="Output JSON")
    return p.parse_args()


def query_metrics(db_path, model, route, window):
    with sqlite3.connect(db_path) as conn:
        where = [f"r.timestamp >= datetime('now', '-{window} minutes')"]
        params = []
        if model != "all":
            where.append("r.model_name = ?")
            params.append(model)
        if route != "all":
            where.append("r.route_name = ?")
            params.append(route)
        wsql = " AND ".join(where)

        row = conn.execute(f"""
            SELECT
                COUNT(*) as total,
                AVG(e.risk_score),
                AVG(e.reliability_score),
                SUM(CASE WHEN e.review_required=1 THEN 1.0 ELSE 0 END)/MAX(COUNT(*),1)*100
            FROM raw_events r
            LEFT JOIN evaluated_events e ON r.event_id = e.event_id
            WHERE {wsql}
        """, params).fetchone()

        total = row[0] or 0
        avg_risk = row[1] or 0
        avg_reliability = row[2] or 0
        review_rate = row[3] or 0

        def label_rate(label):
            n = conn.execute(f"""
                SELECT COUNT(DISTINCT er.event_id)
                FROM evaluator_results er
                JOIN raw_events r ON er.event_id = r.event_id
                WHERE er.label=? AND {wsql}
            """, [label] + params).fetchone()[0]
            return (n / max(1, total)) * 100

        injection_rate = label_rate("prompt_injection")
        sensitive_rate = label_rate("pii_in_prompt") + label_rate("payment_card_in_prompt")
        halluc_rate = label_rate("hallucination_detected")

        latencies = sorted(
            r[0] for r in conn.execute(
                f"SELECT latency_ms FROM raw_events r WHERE {wsql}", params
            ).fetchall()
        )
        n = len(latencies)
        p95 = latencies[int(n * 0.95)] if n > 0 else 0

        drift_alerts = conn.execute(
            "SELECT COUNT(*) FROM drift_alerts WHERE severity='high'"
        ).fetchone()[0]

    return {
        "total_events": total,
        "avg_risk_score": round(avg_risk, 2),
        "avg_reliability_score": round(avg_reliability, 2),
        "review_rate": round(review_rate, 2),
        "p95_latency_ms": round(p95, 2),
        "injection_rate": round(injection_rate, 2),
        "sensitive_data_rate": round(sensitive_rate, 2),
        "hallucination_rate": round(halluc_rate, 2),
        "critical_drift_alerts": drift_alerts,
    }


def run_gate():
    args = parse_args()
    db_path = get_db_path()

    if not os.path.exists(db_path):
        print("❌ ERROR: Database not found. Run `make demo` first.")
        sys.exit(1)

    metrics = query_metrics(db_path, args.model, args.route, args.window)

    thresholds = {
        "max_review_rate":    args.max_review_rate,
        "max_avg_risk_score": args.max_risk,
        "max_p95_latency_ms": args.max_p95_latency,
        "max_injection_rate": args.max_injection,
        "max_sensitive_rate": args.max_sensitive,
        "max_halluc_rate":    args.max_halluc,
        "min_reliability":    args.min_reliability,
    }

    failures = []
    warnings = []

    checks = [
        ("review_rate",             metrics["review_rate"],             thresholds["max_review_rate"],    ">"),
        ("avg_risk_score",          metrics["avg_risk_score"],          thresholds["max_avg_risk_score"], ">"),
        ("p95_latency_ms",          metrics["p95_latency_ms"],          thresholds["max_p95_latency_ms"], ">"),
        ("injection_rate",          metrics["injection_rate"],          thresholds["max_injection_rate"], ">"),
        ("sensitive_data_rate",     metrics["sensitive_data_rate"],     thresholds["max_sensitive_rate"], ">"),
        ("hallucination_rate",      metrics["hallucination_rate"],      thresholds["max_halluc_rate"],    ">"),
        ("avg_reliability_score",   metrics["avg_reliability_score"],   thresholds["min_reliability"],    "<"),
    ]

    for name, value, threshold, op in checks:
        if op == ">" and value > threshold:
            failures.append((name, value, threshold, op))
        elif op == "<" and value < threshold:
            failures.append((name, value, threshold, op))

    if metrics["critical_drift_alerts"] > 0:
        failures.append(("critical_drift_alerts", metrics["critical_drift_alerts"], 0, ">"))

    passed = len(failures) == 0

    if args.json:
        print(json.dumps({
            "passed": passed,
            "model": args.model,
            "route": args.route,
            "window_minutes": args.window,
            "metrics": metrics,
            "thresholds": thresholds,
            "failures": [f"{n}={v:.2f} (threshold={t})" for n, v, t, _ in failures],
        }, indent=2))
        sys.exit(0 if passed else 1)

    # Human-readable report
    width = 64
    print("=" * width)
    print("  AEGISSTREAM DEPLOYMENT GATE REPORT")
    print(f"  Model: {args.model} | Route: {args.route} | Window: {args.window}m")
    print("=" * width)
    print(f"\n  STATUS: {'✅ PASS' if passed else '❌ FAIL'}\n")

    print("  METRICS vs THRESHOLDS")
    print("  " + "-" * 60)
    fmt = "  {:<28} {:>10}  {:>10}  {}"
    print(fmt.format("Metric", "Value", "Threshold", "Status"))
    print("  " + "-" * 60)

    check_map = {n: (v, t, op) for n, v, t, op in checks}
    check_map["critical_drift_alerts"] = (
        metrics["critical_drift_alerts"], 0, ">"
    )

    for name, value, threshold, op in checks + [("critical_drift_alerts", metrics["critical_drift_alerts"], 0, ">")]:
        ok = (value <= threshold if op == ">" else value >= threshold)
        status = "✅" if ok else "❌ FAIL"
        print(fmt.format(name[:27], f"{value:.2f}", f"{threshold:.2f}", status))

    if failures:
        print(f"\n  ❌ BLOCKING REASONS ({len(failures)})")
        print("  " + "-" * 60)
        for name, value, threshold, op in failures:
            direction = "exceeds" if op == ">" else "below"
            print(f"  • {name}: {value:.2f} {direction} threshold {threshold}")

        print("\n  RECOMMENDED ACTIONS:")
        if any(n == "injection_rate" for n, *_ in failures):
            print("  → Review prompt injection patterns; update input sanitization.")
        if any(n == "hallucination_rate" for n, *_ in failures):
            print("  → Audit RAG pipeline; check retrieval quality and prompt templates.")
        if any(n == "review_rate" for n, *_ in failures):
            print("  → Clear review queue backlog; investigate flagged failure modes.")
        if any(n == "avg_risk_score" for n, *_ in failures):
            print("  → Investigate top failure modes; consider guardrail tightening.")
        if any(n == "p95_latency_ms" for n, *_ in failures):
            print("  → Check model serving infrastructure; profile slow requests.")
        if any(n == "critical_drift_alerts" for n, *_ in failures):
            print("  → Investigate drift alerts; behavioral shift detected in traffic.")
    else:
        print("\n  ✅ All metrics within acceptable thresholds.")
        print("  Deployment is approved for this model/route combination.")

    print("\n" + "=" * width)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    run_gate()
