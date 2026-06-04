"""RAG Groundedness Monitor page."""
import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="RAG Groundedness | AegisStream", layout="wide")
st.title("🔍 RAG Groundedness Monitor")
st.caption(
    "Measure how faithfully model responses stay grounded in retrieved context. "
    "Ungrounded responses are a leading source of production hallucinations in RAG pipelines."
)

API_URL = "http://api:8000"


@st.cache_data(ttl=12)
def fetch(ep):
    try:
        return requests.get(f"{API_URL}{ep}", timeout=5).json()
    except Exception:
        return None


# ── KPI Row ──────────────────────────────────────────────────────────────────
overview = fetch("/metrics/overview") or {}
failures = fetch("/metrics/failure-modes?limit=50") or []
df_f = pd.DataFrame(failures) if failures else pd.DataFrame()

def label_count(label):
    if df_f.empty or "label" not in df_f.columns:
        return 0
    row = df_f[df_f["label"] == label]
    return int(row["count"].values[0]) if not row.empty else 0

grounded_count   = label_count("grounded")
weak_count       = label_count("weakly_grounded")
ungrounded_count = label_count("ungrounded_response")
no_rag_count     = label_count("no_rag_context")
total_rag        = grounded_count + weak_count + ungrounded_count

c1, c2, c3, c4 = st.columns(4)
c1.metric("Grounded",   grounded_count,
          help="Response well-supported by retrieved context")
c2.metric("Weakly Grounded", weak_count,
          help="Partial overlap with context; potential drift")
c3.metric("Ungrounded", ungrounded_count,
          help="Response ignores or contradicts retrieved context",
          delta=f"-{ungrounded_count}" if ungrounded_count else None,
          delta_color="inverse")
c4.metric("Avg Groundedness Score",
          f"{overview.get('avg_groundedness_score', 0):.1f}%")

st.divider()

# ── Groundedness breakdown chart ─────────────────────────────────────────────
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Groundedness Distribution")
    if total_rag > 0:
        data = pd.DataFrame({
            "Category": ["Grounded", "Weakly Grounded", "Ungrounded"],
            "Count":    [grounded_count, weak_count, ungrounded_count],
        }).set_index("Category")
        st.bar_chart(data)
    else:
        st.info("No RAG events yet. RAG events include a `retrieved_context` field.")

with col2:
    st.subheader("Groundedness Score Over Time")
    ts = fetch("/metrics/timeseries?minutes=120") or []
    if ts:
        df_ts = pd.DataFrame(ts)
        if not df_ts.empty and "bucket" in df_ts.columns:
            df_ts["bucket"] = pd.to_datetime(df_ts["bucket"])
            df_ts = df_ts.set_index("bucket")
            if "avg_risk" in df_ts.columns:
                # Proxy: invert risk for groundedness trend
                df_ts["groundedness_proxy"] = 100 - df_ts["avg_risk"].fillna(0)
                st.line_chart(df_ts["groundedness_proxy"], color="#22c55e")
                st.caption("Approximate groundedness trend (inverted risk proxy). "
                           "Full groundedness timeseries requires per-event aggregation.")

st.divider()

# ── Route-level groundedness ──────────────────────────────────────────────────
st.subheader("Groundedness by Route")
routes = fetch("/metrics/route-comparison") or []
if routes:
    df_r = pd.DataFrame(routes)
    if not df_r.empty:
        cols = ["route_name", "total_events", "avg_risk", "avg_reliability"]
        cols = [c for c in cols if c in df_r.columns]
        st.dataframe(
            df_r[cols].sort_values("avg_risk", ascending=False).round(2),
            use_container_width=True,
            hide_index=True,
            column_config={
                "avg_risk": st.column_config.ProgressColumn(
                    "Avg Risk", min_value=0, max_value=100, format="%.1f"
                ),
            }
        )
        st.caption(
            "Routes using RAG (e.g. `rag_qa`) should show lower average risk "
            "when the retriever returns high-quality context."
        )

st.divider()

# ── Recent ungrounded events ──────────────────────────────────────────────────
st.subheader("🔴 Recent Ungrounded Events")
events = fetch("/events/recent?limit=100") or []
if events:
    df_e = pd.DataFrame(events)
    if not df_e.empty and "primary_failure_mode" in df_e.columns:
        ungrounded = df_e[df_e["primary_failure_mode"].isin(
            {"ungrounded_response", "weakly_grounded"}
        )]
        if not ungrounded.empty:
            show_cols = [c for c in
                         ["event_id", "model_name", "route_name",
                          "primary_failure_mode", "risk_score"] if c in ungrounded.columns]
            st.dataframe(
                ungrounded[show_cols].round(2),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("✅ No ungrounded responses in the last 100 events.")

st.divider()
st.markdown("""
**What is groundedness?**
In retrieval-augmented generation (RAG), the model receives retrieved documents alongside
the user prompt. A *grounded* response draws its claims directly from that context.
An *ungrounded* response introduces facts not present in the context — which is a primary
mechanism for hallucination in deployed RAG systems. AegisStream measures groundedness
via token-overlap between the retrieved context and the model response (after stop-word removal).
This is a lightweight proxy; semantic groundedness evaluation (e.g., via NLI models) is listed
as future work in `docs/limitations.md`.
""")
