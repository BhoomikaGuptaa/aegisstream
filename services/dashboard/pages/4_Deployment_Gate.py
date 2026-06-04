"""Deployment Readiness Gate page."""
import streamlit as st
import requests

st.set_page_config(page_title="Deployment Gate | AegisStream", layout="wide")
st.title("🚀 Deployment Readiness Gate")
st.caption("CI/CD gate: block risky model or prompt releases before they reach production")

API_URL = "http://api:8000"

col1, col2, col3 = st.columns(3)
model_name = col1.text_input("Model name (or 'all')", "all")
route_name = col2.text_input("Route name (or 'all')", "all")
window = col3.slider("Window (minutes)", 5, 120, 60)

if st.button("🔍 Run Deployment Check", type="primary"):
    try:
        resp = requests.post(f"{API_URL}/deployment/check", json={
            "model_name": model_name,
            "route_name": route_name,
            "window_minutes": window,
        }, timeout=10)
        result = resp.json()

        if result.get("passed"):
            st.success(f"✅ DEPLOYMENT APPROVED — {result['recommendation']}")
        else:
            st.error(f"🚫 DEPLOYMENT BLOCKED — {result['recommendation']}")

        st.divider()

        m = result.get("metrics", {})
        t = result.get("thresholds", {})

        col4, col5, col6 = st.columns(3)
        col4.metric("Review Rate", f"{m.get('review_rate', 0):.1f}%",
                    delta=f"threshold: {t.get('max_review_rate', 15)}%")
        col5.metric("Avg Risk Score", f"{m.get('avg_risk_score', 0):.1f}",
                    delta=f"threshold: {t.get('max_avg_risk_score', 35)}")
        col6.metric("P95 Latency", f"{m.get('p95_latency_ms', 0):.0f} ms",
                    delta=f"threshold: {t.get('max_p95_latency_ms', 3000):.0f}")

        col7, col8, col9 = st.columns(3)
        col7.metric("Injection Rate", f"{m.get('injection_rate', 0):.1f}%")
        col8.metric("Sensitive Data Rate", f"{m.get('sensitive_data_rate', 0):.1f}%")
        col9.metric("Hallucination Rate", f"{m.get('hallucination_rate', 0):.1f}%")

        if result.get("failures"):
            st.subheader("❌ Blocking Reasons")
            for f in result["failures"]:
                st.error(f"• {f}")

        if result.get("warnings"):
            st.subheader("⚠️ Warnings")
            for w in result["warnings"]:
                st.warning(f"• {w}")

    except Exception as e:
        st.error(f"Check failed: {e}")

st.divider()
st.subheader("📋 Current System Readiness")

@st.cache_data(ttl=15)
def get_readiness():
    try:
        return requests.get(f"{API_URL}/deployment/readiness", timeout=5).json()
    except:
        return None

readiness = get_readiness()
if readiness:
    badge = "✅ READY" if readiness.get("passed") else "🚫 NOT READY"
    st.markdown(f"### System Status: {badge}")
    st.json(readiness.get("metrics", {}))
