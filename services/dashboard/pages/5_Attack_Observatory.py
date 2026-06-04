"""Prompt Attack Observatory page."""
import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Attack Observatory | AegisStream", layout="wide")
st.title("🎯 Prompt Attack Observatory")
st.caption("Monitor prompt injection, jailbreak attempts, and adversarial input patterns in real time")

API_URL = "http://api:8000"

@st.cache_data(ttl=10)
def fetch(ep):
    try:
        return requests.get(f"{API_URL}{ep}", timeout=5).json()
    except:
        return None

col1, col2, col3, col4 = st.columns(4)

failures = fetch("/metrics/failure-modes?limit=30") or []
df_f = pd.DataFrame(failures)

def count_label(label):
    if df_f.empty or "label" not in df_f.columns:
        return 0
    row = df_f[df_f["label"] == label]
    return int(row["count"].values[0]) if not row.empty else 0

injection_count = count_label("prompt_injection")
jailbreak_count = count_label("jailbreak_attempt") + count_label("jailbreak_compliance")
compliance_count = count_label("jailbreak_compliance")
sensitive_count = count_label("pii_in_prompt") + count_label("payment_card_in_prompt") + count_label("phi_in_prompt")

col1.metric("Injection Attempts", injection_count)
col2.metric("Jailbreak Attempts", jailbreak_count)
col3.metric("Unsafe Compliance", compliance_count)
col4.metric("Sensitive Data Events", sensitive_count)

st.divider()
st.subheader("Attack Pattern Distribution")
if not df_f.empty:
    attack_labels = [
        "prompt_injection", "jailbreak_attempt", "jailbreak_compliance",
        "unsafe_compliance", "pii_in_prompt", "payment_card_in_prompt",
        "phi_in_prompt", "data_leakage_in_response", "toxic_output",
    ]
    df_attack = df_f[df_f["label"].isin(attack_labels)]
    if not df_attack.empty:
        st.bar_chart(df_attack.set_index("label")["count"])

st.subheader("🔴 Recent Injection / Jailbreak Events")
events = fetch("/events/recent?limit=100") or []
if events:
    df_e = pd.DataFrame(events)
    if not df_e.empty and "primary_failure_mode" in df_e.columns:
        attack_modes = {"prompt_injection", "jailbreak_attempt", "jailbreak_compliance", "unsafe_compliance"}
        df_attacks = df_e[df_e["primary_failure_mode"].isin(attack_modes)]
        if not df_attacks.empty:
            show_cols = ["event_id", "model_name", "primary_failure_mode", "risk_score", "route_name"]
            show_cols = [c for c in show_cols if c in df_attacks.columns]
            st.dataframe(df_attacks[show_cols].round(2), use_container_width=True, hide_index=True)
        else:
            st.info("No recent attack events in the last 100.")

st.divider()
st.subheader("📈 Attack Rate Over Time")
ts = fetch("/metrics/timeseries?minutes=120") or []
if ts:
    df_ts = pd.DataFrame(ts)
    if not df_ts.empty and "bucket" in df_ts.columns:
        df_ts["bucket"] = pd.to_datetime(df_ts["bucket"])
        df_ts = df_ts.set_index("bucket")
        if "reviews" in df_ts.columns:
            st.line_chart(df_ts[["event_count", "reviews"]].dropna())
