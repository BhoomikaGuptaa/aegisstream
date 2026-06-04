"""Latency & Cost Tradeoff Analysis page."""
import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Latency & Cost | AegisStream", layout="wide")
st.title("⚡ Latency & Cost Tradeoff Analysis")
st.caption(
    "Understand the operational cost of reliability. Compare latency, token usage, "
    "and cost efficiency across models and routes."
)

API_URL = "http://api:8000"


@st.cache_data(ttl=15)
def fetch(ep):
    try:
        return requests.get(f"{API_URL}{ep}", timeout=5).json()
    except Exception:
        return None


# ── Latency Percentiles ───────────────────────────────────────────────────────
st.subheader("📊 System-Wide Latency Percentiles")
pct = fetch("/metrics/latency-percentiles") or {}

if pct:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("P50", f"{pct.get('p50', 0):.0f} ms")
    c2.metric("P95", f"{pct.get('p95', 0):.0f} ms",
              delta="SLA: 3000ms", delta_color="off")
    c3.metric("P99", f"{pct.get('p99', 0):.0f} ms")
    c4.metric("Avg", f"{pct.get('avg', 0):.0f} ms")
    c5.metric("Sample Size", f"{pct.get('count', 0):,}")

    # SLA health indicator
    p95 = pct.get("p95", 0)
    if p95 > 5000:
        st.error(f"🔴 P95 latency {p95:.0f}ms is CRITICAL (>5000ms). Check model serving infrastructure.")
    elif p95 > 3000:
        st.warning(f"🟡 P95 latency {p95:.0f}ms exceeds SLA warning threshold (3000ms).")
    else:
        st.success(f"✅ P95 latency {p95:.0f}ms within SLA.")

st.divider()

# ── Model-level latency and cost comparison ───────────────────────────────────
col1, col2 = st.columns(2)

models = fetch("/metrics/model-comparison") or []
df_m = pd.DataFrame(models) if models else pd.DataFrame()

with col1:
    st.subheader("Latency by Model (avg ms)")
    if not df_m.empty and "avg_latency_ms" in df_m.columns:
        chart_data = df_m[["model_name", "avg_latency_ms"]].set_index("model_name")
        st.bar_chart(chart_data)
    else:
        st.info("No model data yet.")

with col2:
    st.subheader("Cost per Request by Model (USD)")
    if not df_m.empty and "avg_cost" in df_m.columns:
        chart_data = df_m[["model_name", "avg_cost"]].set_index("model_name")
        st.bar_chart(chart_data)
    else:
        st.info("No cost data yet.")

st.divider()

# ── Latency vs reliability scatter (approximated) ─────────────────────────────
st.subheader("📈 Latency & Risk Trend (rolling)")
ts = fetch("/metrics/timeseries?minutes=120") or []
if ts:
    df_ts = pd.DataFrame(ts)
    if not df_ts.empty and "bucket" in df_ts.columns:
        df_ts["bucket"] = pd.to_datetime(df_ts["bucket"])
        df_ts = df_ts.set_index("bucket")
        if "avg_latency" in df_ts.columns and "avg_risk" in df_ts.columns:
            st.line_chart(df_ts[["avg_latency", "avg_risk"]].dropna())
            st.caption("Blue = avg latency (ms) | Red = avg risk score. "
                       "Latency spikes often co-occur with high-cost or malformed requests.")

st.divider()

# ── Full model scorecard with cost and latency ────────────────────────────────
st.subheader("Full Model Scorecard")
overview = fetch("/metrics/overview") or {}
if not df_m.empty:
    display_cols = [c for c in [
        "model_name", "provider", "total_events",
        "avg_latency_ms", "avg_cost", "avg_risk",
        "avg_reliability", "avg_safety", "review_rate"
    ] if c in df_m.columns]

    st.dataframe(
        df_m[display_cols].round(4).sort_values("avg_latency_ms")
        if "avg_latency_ms" in df_m.columns else df_m[display_cols].round(4),
        use_container_width=True,
        hide_index=True,
        column_config={
            "avg_cost": st.column_config.NumberColumn(
                "Avg Cost (USD)", format="$%.5f"
            ),
            "avg_latency_ms": st.column_config.NumberColumn(
                "Avg Latency (ms)", format="%.0f ms"
            ),
            "avg_risk": st.column_config.ProgressColumn(
                "Avg Risk", min_value=0, max_value=100
            ),
        }
    )

st.divider()

# ── Route latency comparison ──────────────────────────────────────────────────
st.subheader("Latency & Risk by Route")
routes = fetch("/metrics/route-comparison") or []
if routes:
    df_r = pd.DataFrame(routes)
    if not df_r.empty and "avg_latency_ms" in df_r.columns:
        st.bar_chart(df_r[["route_name", "avg_latency_ms"]].set_index("route_name"))

# ── Cost projections ──────────────────────────────────────────────────────────
st.divider()
st.subheader("💰 Cost Projections")

total_cost = overview.get("total_cost_usd", 0)
avg_cost   = overview.get("avg_cost_usd", 0)
total_ev   = overview.get("total_events", 1)

c1, c2, c3 = st.columns(3)
c1.metric("Total Cost (all events)",  f"${total_cost:.4f}")
c2.metric("Avg Cost per Request",     f"${avg_cost:.6f}")
c3.metric("Projected / 1M requests",  f"${avg_cost * 1_000_000:.2f}")

if avg_cost > 0:
    st.markdown(f"""
| Scale | Projected Cost |
|---|---|
| 10K requests | ${avg_cost * 10_000:.2f} |
| 100K requests | ${avg_cost * 100_000:.2f} |
| 1M requests | ${avg_cost * 1_000_000:.2f} |
| 10M requests | ${avg_cost * 10_000_000:.2f} |
""")
    st.caption("Projections based on current average cost. Actual costs vary by model, "
               "prompt length, and provider pricing.")
