"""Drift and Regression Detection page."""
import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Drift Detection | AegisStream", layout="wide")
st.title("📡 Drift & Regression Detection")
st.caption("Detect rising adversarial traffic, hallucination rate drift, and behavioral regressions in real time")

API_URL = "http://api:8000"

@st.cache_data(ttl=8)
def fetch(ep):
    try:
        return requests.get(f"{API_URL}{ep}", timeout=5).json()
    except:
        return None

alerts = fetch("/metrics/drift?limit=20") or []
if alerts:
    st.subheader(f"🚨 {len(alerts)} Drift Alert(s) Detected")
    for a in alerts:
        sev = a.get("severity", "medium")
        icon = "🔴" if sev == "high" else "🟡"
        with st.expander(f"{icon} [{sev.upper()}] {a.get('alert_type','?')} — {a.get('message','')[:80]}"):
            col1, col2, col3 = st.columns(3)
            col1.metric("Current Value", f"{a.get('current_value', 0):.2f}")
            col2.metric("Baseline", f"{a.get('baseline_value', 0):.2f}")
            col3.metric("Threshold", f"{a.get('threshold', 0):.2f}")
            st.caption(f"Model: {a.get('model_name','all')} | Metric: {a.get('metric_name','?')} | {a.get('detected_at','?')}")
else:
    st.success("✅ No active drift alerts.")

st.divider()
st.subheader("📈 Rolling Risk Score Trend")
ts = fetch("/metrics/timeseries?minutes=180") or []
if ts:
    df = pd.DataFrame(ts)
    if not df.empty and "bucket" in df.columns:
        df["bucket"] = pd.to_datetime(df["bucket"])
        df = df.set_index("bucket")
        if "avg_risk" in df.columns:
            st.line_chart(df["avg_risk"].dropna(), color="#ef4444")
        st.caption("Red zone indicates potential drift if risk score exceeds 2.5x baseline (~37)")

st.subheader("📊 Failure Mode Trend")
failures = fetch("/metrics/failure-modes") or []
if failures:
    df_f = pd.DataFrame(failures)
    if not df_f.empty:
        st.dataframe(df_f.sort_values("count", ascending=False).round(2),
                     use_container_width=True, hide_index=True)
