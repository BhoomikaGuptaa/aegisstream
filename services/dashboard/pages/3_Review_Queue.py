"""Human Review Queue page."""
import streamlit as st
import requests

st.set_page_config(page_title="Review Queue | AegisStream", layout="wide")
st.title("👁️ Human Review Queue")
st.caption("Review and triage flagged LLM outputs")

API_URL = "http://api:8000"

status_filter = st.selectbox("Filter by status", ["pending", "approved", "rejected", "escalated"])

@st.cache_data(ttl=5)
def get_reviews(status):
    try:
        return requests.get(f"{API_URL}/reviews/?status={status}&limit=50", timeout=5).json()
    except:
        return []

reviews = get_reviews(status_filter)

if not reviews:
    st.info(f"No {status_filter} reviews.")
    st.stop()

st.markdown(f"**{len(reviews)} items** with status: `{status_filter}`")

for item in reviews:
    risk = item.get("risk_score", 0)
    color = "#ef4444" if risk > 60 else "#f97316" if risk > 40 else "#eab308"
    fm = item.get("primary_failure_mode", "unknown")

    with st.expander(
        f"🔴 [{risk:.0f}] {fm} | {item.get('model_name','?')} | {item.get('route_name','?')} | {item.get('event_id','?')[:12]}"
    ):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Prompt:**")
            st.code(item.get("prompt", "")[:400], language=None)
        with col2:
            st.markdown("**Response:**")
            st.code(item.get("response", "")[:400], language=None)

        st.markdown(f"Risk: `{risk:.1f}` | Safety: `{item.get('safety_score', '?')}` | Failure: `{fm}`")

        if status_filter == "pending":
            cols = st.columns(3)
            new_status = None
            notes = st.text_input("Notes", key=f"notes_{item['event_id']}")
            if cols[0].button("✅ Approve", key=f"app_{item['event_id']}"):
                new_status = "approved"
            if cols[1].button("❌ Reject", key=f"rej_{item['event_id']}"):
                new_status = "rejected"
            if cols[2].button("⚠️ Escalate", key=f"esc_{item['event_id']}"):
                new_status = "escalated"

            if new_status:
                try:
                    requests.patch(
                        f"{API_URL}/reviews/{item['event_id']}",
                        json={"review_status": new_status, "reviewer_notes": notes},
                        timeout=5,
                    )
                    st.success(f"Marked as {new_status}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")
