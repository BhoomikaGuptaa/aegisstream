"""Model Comparison Lab page."""
import sys
sys.path.insert(0, "/app")

import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Model Comparison | AegisStream", layout="wide")
st.title("🧪 Model Comparison Lab")
st.caption("Compare reliability, safety, cost, and latency across open-source models")

API_URL = "http://api:8000"

@st.cache_data(ttl=15)
def fetch(ep):
    try:
        return requests.get(f"{API_URL}{ep}", timeout=5).json()
    except:
        return None

models = fetch("/metrics/model-comparison")
if not models:
    st.warning("No model data yet. Run `make demo` to seed events.")
    st.stop()

df = pd.DataFrame(models)

st.subheader("📊 Model Scorecard")
st.dataframe(
    df.round(2),
    use_container_width=True,
    hide_index=True,
    column_config={
        "avg_risk": st.column_config.ProgressColumn("Avg Risk", min_value=0, max_value=100),
        "avg_reliability": st.column_config.ProgressColumn("Reliability", min_value=0, max_value=100),
        "avg_safety": st.column_config.ProgressColumn("Safety", min_value=0, max_value=100),
        "review_rate": st.column_config.NumberColumn("Review Rate %", format="%.1f%%"),
    }
)

if not df.empty and "avg_risk" in df.columns:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Risk by Model")
        st.bar_chart(df.set_index("model_name")["avg_risk"])
    with col2:
        st.subheader("Avg Latency by Model (ms)")
        if "avg_latency_ms" in df.columns:
            st.bar_chart(df.set_index("model_name")["avg_latency_ms"])

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Safety Score by Model")
        if "avg_safety" in df.columns:
            st.bar_chart(df.set_index("model_name")["avg_safety"])
    with col4:
        st.subheader("Cost per Request by Model")
        if "avg_cost" in df.columns:
            st.bar_chart(df.set_index("model_name")["avg_cost"])
