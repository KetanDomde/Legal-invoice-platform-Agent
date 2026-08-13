import pandas as pd
import streamlit as st

from utils.theme import inject_base_css, render_banner
from utils.api_client import get_client, require_role, APIError

st.set_page_config(page_title="Audit Log | Konverge", page_icon="📜", layout="wide")
inject_base_css()
require_role("admin", "editor")
render_banner("Audit Log", subtitle="Every submit, validate, approve, reject, and clarify action — who did what, when.")

client = get_client()

col1, col2 = st.columns(2)
with col1:
    invoice_filter = st.text_input("Filter by invoice ID (optional)")
with col2:
    user_filter = st.text_input("Filter by user ID (optional)")

try:
    logs = client.list_audit_logs(
        invoice_id=int(invoice_filter) if invoice_filter.strip().isdigit() else None,
        user_id=int(user_filter) if user_filter.strip().isdigit() else None,
    )
except APIError as e:
    st.error(f"Couldn't load audit logs: {e.detail}")
    st.stop()

if not logs:
    st.info("No audit entries match this filter.")
else:
    df = pd.DataFrame(logs)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.sort_values("created_at", ascending=False)
    st.dataframe(
        df.rename(columns={
            "audit_id": "ID", "invoice_id": "Invoice", "user_id": "User",
            "action": "Action", "notes": "Notes", "created_at": "When",
        }),
        use_container_width=True, hide_index=True,
    )
