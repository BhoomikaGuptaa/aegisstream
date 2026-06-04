"""Research Experiment Report page."""
import streamlit as st
import requests
import json
import os

st.set_page_config(page_title="Experiment Report | AegisStream", layout="wide")
st.title("🔬 Research Experiment Report")
st.caption(
    "Run and inspect reproducible experiments comparing models, evaluator ablations, "
    "throughput benchmarks, and failure-mode simulations."
)

API_URL = "http://api:8000"

# ── Run experiments via API ───────────────────────────────────────────────────
st.subheader("Run Experiment Suite")
st.markdown("""
Experiments run in-process (no Kafka required). Each experiment generates
a configurable number of synthetic events, evaluates them, and reports aggregate statistics.
""")

col1, col2 = st.columns([2, 1])
with col1:
    exp_choice = st.selectbox(
        "Experiment",
        options=["throughput", "latency", "failure", "models", "ablation", "all"],
        help="Select which experiment to run",
    )
with col2:
    st.markdown("&nbsp;")
    run_btn = st.button("▶ Run Experiment", type="primary")

if run_btn:
    with st.spinner(f"Running '{exp_choice}' experiment... (~10–30 seconds)"):
        try:
            # The experiment runner is a script; call it via subprocess in the API container
            import subprocess, sys
            result = subprocess.run(
                [sys.executable, "scripts/run_experiments.py",
                 "--experiment", exp_choice,
                 "--output", "/data/last_experiment.json"],
                capture_output=True, text=True, timeout=120,
                cwd="/app",
            )
            st.text_area("Experiment Output", result.stdout + result.stderr,
                         height=300)
            if result.returncode == 0:
                st.success("✅ Experiment complete. Results saved to `/data/last_experiment.json`.")
            else:
                st.error(f"Experiment failed (exit {result.returncode})")
        except Exception as e:
            st.error(f"Could not run experiment: {e}")
            st.info("Run manually: `docker compose exec api python scripts/run_experiments.py`")

st.divider()

# ── Load last saved results ───────────────────────────────────────────────────
st.subheader("📊 Last Experiment Results")
results_path = "/data/last_experiment.json"

if os.path.exists(results_path):
    with open(results_path) as f:
        results = json.load(f)

    if "meta" in results:
        st.caption(f"Run at: {results['meta'].get('timestamp','?')} | "
                   f"Total time: {results['meta'].get('total_elapsed_sec','?')}s")

    import pandas as pd

    if "throughput" in results:
        st.subheader("Throughput Benchmark")
        rows = [{"n_events": k, **v} for k, v in results["throughput"].items()]
        df = pd.DataFrame(rows)
        st.dataframe(df.round(2), use_container_width=True, hide_index=True)

    if "model_comparison" in results:
        st.subheader("Model Comparison")
        rows = [{"model": k, **v} for k, v in results["model_comparison"].items()]
        df = pd.DataFrame(rows)
        show = [c for c in ["model","avg_risk_score","avg_reliability_score",
                             "review_rate_pct","blocking_rate_pct","throughput_eps"]
                if c in df.columns]
        st.dataframe(df[show].round(2), use_container_width=True, hide_index=True)
        if "avg_risk_score" in df.columns:
            st.bar_chart(df[["model","avg_risk_score"]].set_index("model"))

    if "failure_simulation" in results:
        st.subheader("Failure Mode Simulation")
        rows = [{"scenario": k, **v} for k, v in results["failure_simulation"].items()]
        df = pd.DataFrame(rows)
        show = [c for c in ["scenario","avg_risk_score","review_rate_pct","blocking_rate_pct"]
                if c in df.columns]
        st.dataframe(df[show].round(2), use_container_width=True, hide_index=True)

    if "guardrail_ablation" in results:
        st.subheader("Guardrail Ablation Study")
        rows = [{"config": k, **v} for k, v in results["guardrail_ablation"].items()]
        df = pd.DataFrame(rows)
        show = [c for c in ["config","avg_risk_score","review_rate_pct","blocking_rate_pct"]
                if c in df.columns]
        st.dataframe(df[show].round(2), use_container_width=True, hide_index=True)
        st.caption(
            "Ablation study: removing evaluators shows how much missed-risk increases. "
            "review_rate_pct decreases when evaluators are removed — but so does detected risk."
        )

    if "evaluator_latency" in results:
        st.subheader("Per-Evaluator Latency (ms)")
        rows = [{"evaluator": k, **v} for k, v in results["evaluator_latency"].items()]
        df = pd.DataFrame(rows).sort_values("avg_ms")
        st.dataframe(df.round(4), use_container_width=True, hide_index=True)

else:
    st.info("No experiment results found yet. Run an experiment above or use `make benchmark`.")

st.divider()

# ── Research questions reminder ───────────────────────────────────────────────
with st.expander("📋 Research Questions (AegisStream SOAR Submission)"):
    st.markdown("""
1. **Can lightweight online evaluators identify LLM outputs requiring human review?**
   — Measurable via review_rate vs blocking_rate in the throughput and model comparison experiments.

2. **Which failure modes are easiest and hardest to detect from prompt-response telemetry alone?**
   — The failure simulation experiment sweeps injection and hallucination rates; per-evaluator precision
   can be estimated from the ablation study.

3. **How do open-source models differ in reliability, safety, and cost under simulated live traffic?**
   — Directly addressed by the model comparison experiment (GPT-4o, Claude, Llama, Mistral, Gemma).

4. **Can streaming drift signals detect rising adversarial traffic or hallucination rates?**
   — The drift detector fires when rolling avg risk > 2.5x baseline; testable by running
   the failure simulation with drift_enabled=True.

5. **Can deployment readiness gates reduce risky releases without blocking too many safe outputs?**
   — Configurable thresholds on the deployment gate; the ablation study shows precision-recall tradeoff.
""")
