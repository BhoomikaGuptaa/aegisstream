#!/usr/bin/env python3
"""
AegisStream Research Experiment Runner
=======================================
Run configurable experiments comparing models, evaluator ablations,
throughput benchmarks, and failure-mode simulations.
"""
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "/data/aegisstream.db")

from services.producer.app.synthetic_generator import SyntheticGenerator
from services.evaluator.app.evaluators import ALL_EVALUATORS
from services.evaluator.app.scoring import compute_scores


def run_batch(generator, n_events, evaluators=None):
    """Run N events through the pipeline and return aggregate stats."""
    if evaluators is None:
        evaluators = ALL_EVALUATORS

    results = []
    t0 = time.monotonic()
    for _ in range(n_events):
        event = generator.generate()
        eval_results = [ev.evaluate(event) for ev in evaluators]
        evaluated = compute_scores(event, eval_results)
        results.append(evaluated)
    elapsed = time.monotonic() - t0

    n = len(results)
    avg_risk = sum(r.risk_score for r in results) / n
    avg_reliability = sum(r.reliability_score for r in results) / n
    avg_safety = sum(r.safety_score for r in results) / n
    review_rate = sum(1 for r in results if r.review_required) / n * 100
    blocking_rate = sum(1 for r in results if r.deployment_blocking) / n * 100
    throughput = n / elapsed

    failure_modes = {}
    for r in results:
        if r.primary_failure_mode:
            failure_modes[r.primary_failure_mode] = failure_modes.get(r.primary_failure_mode, 0) + 1

    return {
        "n_events": n,
        "elapsed_sec": round(elapsed, 3),
        "throughput_eps": round(throughput, 1),
        "avg_risk_score": round(avg_risk, 2),
        "avg_reliability_score": round(avg_reliability, 2),
        "avg_safety_score": round(avg_safety, 2),
        "review_rate_pct": round(review_rate, 2),
        "blocking_rate_pct": round(blocking_rate, 2),
        "top_failure_modes": dict(sorted(failure_modes.items(), key=lambda x: -x[1])[:5]),
    }


# ---------------------------------------------------------------------------
# Experiment 1: Throughput Benchmark
# ---------------------------------------------------------------------------

def experiment_throughput():
    print("\n" + "="*60)
    print("EXPERIMENT 1: Throughput Benchmark")
    print("="*60)
    results = {}
    for n in [500, 2000, 5000]:
        gen = SyntheticGenerator(drift_enabled=False)
        print(f"  Running {n} events...", end="", flush=True)
        r = run_batch(gen, n)
        results[str(n)] = r
        print(f" {r['throughput_eps']:.0f} events/sec | {r['elapsed_sec']:.2f}s")
    return results


# ---------------------------------------------------------------------------
# Experiment 2: Evaluator Latency Benchmark
# ---------------------------------------------------------------------------

def experiment_evaluator_latency():
    print("\n" + "="*60)
    print("EXPERIMENT 2: Evaluator Latency Benchmark")
    print("="*60)
    gen = SyntheticGenerator(drift_enabled=False)
    events = [gen.generate() for _ in range(200)]
    per_evaluator = {}

    for ev in ALL_EVALUATORS:
        t0 = time.monotonic()
        for event in events:
            ev.evaluate(event)
        elapsed = time.monotonic() - t0
        per_evaluator[ev.name] = {
            "avg_ms": round(elapsed / len(events) * 1000, 4),
            "total_ms": round(elapsed * 1000, 2),
        }
        print(f"  {ev.name:<35} avg={per_evaluator[ev.name]['avg_ms']:.4f}ms")

    return per_evaluator


# ---------------------------------------------------------------------------
# Experiment 3: Failure Mode Simulation
# ---------------------------------------------------------------------------

def experiment_failure_simulation():
    print("\n" + "="*60)
    print("EXPERIMENT 3: Failure Mode Simulation")
    print("="*60)
    configs = [
        ("baseline",       dict(injection_rate=0.02, hallucination_rate=0.05)),
        ("high_injection", dict(injection_rate=0.20, hallucination_rate=0.05)),
        ("high_halluc",    dict(injection_rate=0.02, hallucination_rate=0.25)),
        ("combined_high",  dict(injection_rate=0.15, hallucination_rate=0.20)),
    ]
    results = {}
    for name, kwargs in configs:
        gen = SyntheticGenerator(**kwargs, drift_enabled=False)
        r = run_batch(gen, 300)
        results[name] = r
        print(f"  {name:<20} risk={r['avg_risk_score']:.1f} | review={r['review_rate_pct']:.1f}% | blocking={r['blocking_rate_pct']:.1f}%")
    return results


# ---------------------------------------------------------------------------
# Experiment 4: Model Comparison
# ---------------------------------------------------------------------------

def experiment_model_comparison():
    print("\n" + "="*60)
    print("EXPERIMENT 4: Model Comparison")
    print("="*60)
    models = {
        "gpt-4o":         {"gpt-4o": 1.0},
        "claude-3-sonnet": {"claude-3-sonnet": 1.0},
        "llama-3-70b":    {"llama-3-70b": 1.0},
        "mistral-7b":     {"mistral-7b": 1.0},
        "gemma-7b":       {"gemma-7b": 1.0},
    }
    results = {}
    for model_name, weights in models.items():
        gen = SyntheticGenerator(model_weights=weights, drift_enabled=False)
        r = run_batch(gen, 200)
        results[model_name] = r
        print(f"  {model_name:<20} risk={r['avg_risk_score']:.1f} | reliability={r['avg_reliability_score']:.1f} | review={r['review_rate_pct']:.1f}%")
    return results


# ---------------------------------------------------------------------------
# Experiment 5: Guardrail Ablation
# ---------------------------------------------------------------------------

def experiment_guardrail_ablation():
    print("\n" + "="*60)
    print("EXPERIMENT 5: Guardrail Ablation Study")
    print("="*60)
    from services.evaluator.app.evaluators import (
        PromptInjectionEvaluator, GroundednessEvaluator, RefusalQualityEvaluator,
    )
    all_ev = ALL_EVALUATORS
    no_groundedness = [e for e in ALL_EVALUATORS if not isinstance(e, GroundednessEvaluator)]
    no_injection    = [e for e in ALL_EVALUATORS if not isinstance(e, PromptInjectionEvaluator)]
    no_refusal      = [e for e in ALL_EVALUATORS if not isinstance(e, RefusalQualityEvaluator)]

    configs = [
        ("all_evaluators",        all_ev),
        ("no_groundedness",       no_groundedness),
        ("no_injection_eval",     no_injection),
        ("no_refusal_eval",       no_refusal),
    ]
    gen = SyntheticGenerator(injection_rate=0.10, rag_ungrounded_rate=0.10, drift_enabled=False)
    results = {}
    for name, evaluators in configs:
        r = run_batch(gen, 300, evaluators=evaluators)
        results[name] = r
        missed = 100.0 - r["review_rate_pct"]
        print(f"  {name:<25} review={r['review_rate_pct']:.1f}% | missed_risk_proxy={missed:.1f}%")
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--experiment", default="all",
                   choices=["all", "throughput", "latency", "failure", "models", "ablation"])
    p.add_argument("--output", default=None, help="Save JSON results to file")
    args = p.parse_args()

    all_results = {}
    t_start = time.monotonic()

    if args.experiment in ("all", "throughput"):
        all_results["throughput"] = experiment_throughput()
    if args.experiment in ("all", "latency"):
        all_results["evaluator_latency"] = experiment_evaluator_latency()
    if args.experiment in ("all", "failure"):
        all_results["failure_simulation"] = experiment_failure_simulation()
    if args.experiment in ("all", "models"):
        all_results["model_comparison"] = experiment_model_comparison()
    if args.experiment in ("all", "ablation"):
        all_results["guardrail_ablation"] = experiment_guardrail_ablation()

    total_time = time.monotonic() - t_start
    all_results["meta"] = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_elapsed_sec": round(total_time, 2),
    }

    print(f"\n✅ All experiments complete in {total_time:.1f}s")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"   Results saved to {args.output}")
    else:
        print("\nRun with --output results.json to save full results.")
