import pandas as pd
import streamlit as st

from utils.theme import inject_base_css, page_header, sidebar_brand
from utils.api_client import get_client, require_role, APIError

st.set_page_config(page_title="Audit Log | Konverge", page_icon="📜", layout="wide")
inject_base_css()
sidebar_brand()
require_role("admin", "editor")

page_header(9, "Audit Log", "Every submit, validate, approve, reject, and clarify action — who did what, when.")

client = get_client()

col1, col2 = st.columns([3, 1])
with col1:
    generic_filter = st.text_input(
        "Filter by audit log fields",
        placeholder="notes ilike 'INV291-NS' and created_at >= '2026-08-20 05:27:41'",
    )
with col2:
    quick_limit = st.number_input("Limit", min_value=1, max_value=1000, value=100, step=10)

try:
    logs = client.list_audit_logs(filter=generic_filter or None, limit=quick_limit)
except APIError as e:
    st.error(f"Couldn't load audit logs: {e.detail}")
    st.stop()

if not logs:
    st.info("No audit entries match this filter.")
else:
    df = pd.DataFrame(logs)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.sort_values("created_at", ascending=False)
    # Prefer showing `user_name` when available. Keep `user_id` in the raw data
    # but hide it from the UI by creating a separate view DataFrame for display.
    display_df = df.copy()
    if "user_name" in display_df.columns:
        display_df["User"] = display_df["user_name"]
    else:
        display_df["User"] = ""

    # Create a view that omits `user_id`/`user_name` but keeps raw `display_df` intact
    view_df = display_df.copy()
    for col in ("user_id", "user_name"):
        if col in view_df.columns:
            view_df = view_df.drop(columns=[col])

    # Reorder columns so `User` is shown right after `Invoice` when present
    preferred_order = ["audit_id", "invoice_id", "User", "action", "notes", "created_at"]
    present = [c for c in preferred_order if c in view_df.columns]
    # keep any other columns after the preferred ones
    others = [c for c in view_df.columns if c not in present]
    view_df = view_df[present + others]

    st.dataframe(
        view_df,
        use_container_width=True, hide_index=True,
    )
