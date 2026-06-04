"""
AegisStream Dashboard
Real-Time Behavioral Evaluation Observatory
"""
import sys
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared")

import streamlit as st

st.set_page_config(
    page_title="AegisStream",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }
    .main-header {
        font-family: 'JetBrains Mono', monospace;
        font-size: 2.2rem;
        font-weight: 700;
        color: #00D4AA;
        letter-spacing: -0.02em;
    }
    .sub-header {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.9rem;
        color: #888;
        margin-top: -10px;
    }
    .metric-card {
        background: #0e1117;
        border: 1px solid #1f2937;
        border-radius: 8px;
        padding: 16px;
    }
    .risk-critical { color: #ef4444; font-weight: 700; }
    .risk-high     { color: #f97316; font-weight: 600; }
    .risk-medium   { color: #eab308; }
    .risk-low      { color: #22c55e; }
    div[data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 1.6rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### 🛡️ AegisStream")
    st.markdown("*Real-Time LLM Reliability Observatory*")
    st.divider()

    api_url = st.text_input("API URL", value="http://api:8000")
    refresh_sec = st.slider("Auto-refresh (sec)", 5, 60, 10)

    st.divider()
    st.markdown("**Navigation**")
    st.markdown("""
- 📊 Live Overview ← *this page*
- Use the **Pages** menu above ↑
    """)
    st.divider()
    st.caption("AegisStream v1.0.0 | EleutherAI SOAR")

# Landing page - Live Overview
st.markdown('<div class="main-header">🛡️ AegisStream</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Real-Time Behavioral Evaluation & Reliability Observatory for Open-Source LLMs</div>', unsafe_allow_html=True)
st.divider()

import requests
import time

@st.cache_data(ttl=refresh_sec)
def fetch(endpoint: str):
    try:
        r = requests.get(f"{api_url}{endpoint}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return None

overview = fetch("/metrics/overview")

if not overview:
    st.warning("⏳ Waiting for API and data... Start the stack with `make up` and `make demo`.")
    st.stop()

# Top KPI row
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Events",    f"{overview['total_events']:,}")
c2.metric("Avg Risk Score",  f"{overview['avg_risk_score']:.1f}",
          delta=None, help="0–100, lower is better")
c3.metric("Reliability",     f"{overview['avg_reliability_score']:.1f}%")
c4.metric("Review Queue",    f"{overview['review_queue_pending']:,}",
          delta=f"{overview['review_rate']:.1f}% rate")
c5.metric("Avg Latency",     f"{overview['avg_latency_ms']:.0f} ms")
c6.metric("Total Cost",      f"${overview['total_cost_usd']:.4f}")

st.divider()

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📈 Risk & Reliability Over Time")
    ts = fetch(f"/metrics/timeseries?minutes=60")
    if ts:
        import pandas as pd
        df = pd.DataFrame(ts)
        if not df.empty and "bucket" in df.columns:
            df["bucket"] = pd.to_datetime(df["bucket"])
            df = df.set_index("bucket")
            if "avg_risk" in df.columns and "avg_reliability" in df.columns:
                st.line_chart(df[["avg_risk", "avg_reliability"]].dropna())
    else:
        st.info("No timeseries data yet.")

with col2:
    st.subheader("🎯 Risk Distribution")
    dist = fetch("/metrics/risk-distribution")
    if dist:
        import pandas as pd
        df_dist = pd.DataFrame(dist)
        if not df_dist.empty:
            st.bar_chart(df_dist.set_index("bucket")["count"])
    else:
        st.info("No distribution data yet.")

st.divider()

col3, col4 = st.columns(2)

with col3:
    st.subheader("🤖 Model Comparison")
    models = fetch("/metrics/model-comparison")
    if models:
        import pandas as pd
        df_m = pd.DataFrame(models)
        if not df_m.empty:
            cols = ["model_name", "total_events", "avg_risk", "avg_reliability",
                    "avg_safety", "avg_latency_ms", "review_rate"]
            cols_present = [c for c in cols if c in df_m.columns]
            st.dataframe(
                df_m[cols_present].round(2),
                use_container_width=True,
                hide_index=True,
            )

with col4:
    st.subheader("⚠️ Top Failure Modes")
    failures = fetch("/metrics/failure-modes")
    if failures:
        import pandas as pd
        df_f = pd.DataFrame(failures)
        if not df_f.empty:
            st.dataframe(df_f[["label", "count", "max_severity"]],
                         use_container_width=True, hide_index=True)

st.divider()

st.subheader("🔴 Recent High-Risk Events")
events = fetch("/events/recent?limit=20")
if events:
    import pandas as pd
    df_e = pd.DataFrame(events)
    if not df_e.empty:
        cols_show = ["event_id", "model_name", "route_name", "risk_score",
                     "primary_failure_mode", "review_required", "latency_ms"]
        cols_present = [c for c in cols_show if c in df_e.columns]
        df_show = df_e[cols_present].copy()
        if "risk_score" in df_show.columns:
            df_show = df_show.sort_values("risk_score", ascending=False)
        st.dataframe(df_show.head(15).round(2), use_container_width=True, hide_index=True)

# Auto-refresh
time.sleep(0.1)
st.caption(f"⟳ Auto-refreshing every {refresh_sec}s | Data from {api_url}")
