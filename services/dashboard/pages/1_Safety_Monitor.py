"""Risk & Safety Monitor page."""
import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Safety Monitor | AegisStream", layout="wide")
st.title("🔐 Risk & Safety Monitor")
st.caption("Deep dive into safety scores, failure mode distributions, and flagged outputs")

API_URL = "http://api:8000"


@st.cache_data(ttl=10)
def fetch(ep):
    try:
        return requests.get(f"{API_URL}{ep}", timeout=5).json()
    except Exception:
        return None


overview = fetch("/metrics/overview") or {}
failures = fetch("/metrics/failure-modes?limit=20") or []
df_f = pd.DataFrame(failures) if failures else pd.DataFrame()

# ── KPI Row ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Avg Risk Score",     f"{overview.get('avg_risk_score', 0):.1f} / 100",
          help="0 = no risk, 100 = maximum risk")
c2.metric("Avg Safety Score",   f"{overview.get('avg_safety_score', 0):.1f}%")
c3.metric("Avg Reliability",    f"{overview.get('avg_reliability_score', 0):.1f}%")
c4.metric("Deployment Blocked", f"{overview.get('deployment_blocking_events', 0):,}",
          delta="events", delta_color="off")
c5.metric("Pending Reviews",    f"{overview.get('review_queue_pending', 0):,}")

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("⚠️ Top Failure Modes")
    if not df_f.empty:
        st.dataframe(
            df_f[["label","count","max_severity","avg_delta"]].round(2)
            if "avg_delta" in df_f.columns
            else df_f[["label","count","max_severity"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No failure data yet.")

with col2:
    st.subheader("🎯 Risk Distribution")
    dist = fetch("/metrics/risk-distribution") or []
    if dist:
        df_d = pd.DataFrame(dist).set_index("bucket")
        st.bar_chart(df_d["count"])

st.divider()
st.subheader("📈 Safety & Risk Over Time")
ts = fetch("/metrics/timeseries?minutes=120") or []
if ts:
    df_ts = pd.DataFrame(ts)
    if not df_ts.empty and "bucket" in df_ts.columns:
        df_ts["bucket"] = pd.to_datetime(df_ts["bucket"])
        df_ts = df_ts.set_index("bucket")
        cols = [c for c in ["avg_risk","avg_safety"] if c in df_ts.columns]
        if cols:
            st.line_chart(df_ts[cols].dropna())

st.divider()
st.subheader("🔴 High-Risk Events")
events = fetch("/events/recent?limit=100") or []
if events:
    df_e = pd.DataFrame(events)
    if not df_e.empty and "risk_score" in df_e.columns:
        high_risk = df_e[df_e["risk_score"] >= 40].copy()
        if not high_risk.empty:
            show = [c for c in ["event_id","model_name","route_name","risk_score",
                                 "primary_failure_mode","review_required"] if c in high_risk.columns]
            st.dataframe(
                high_risk[show].sort_values("risk_score", ascending=False).head(20).round(2),
                use_container_width=True, hide_index=True,
            )
        else:
            st.success("✅ No high-risk events in the last 100.")
