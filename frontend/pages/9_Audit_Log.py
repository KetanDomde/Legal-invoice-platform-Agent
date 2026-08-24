import pandas as pd
import streamlit as st

from utils.theme import inject_base_css, page_header, sidebar_brand
from utils.api_client import get_client, require_role, APIError

st.set_page_config(page_title="Audit Log | Konverge", page_icon="📜", layout="wide")
inject_base_css()
sidebar_brand()
require_role("admin", "editor")

page_header(
    9,
    "Audit Log",
    "Trace every action with the business context an administrator actually needs: request, invoice, firm, matter, user, and outcome.",
)

client = get_client()

col1, col2 = st.columns([3, 1])
with col1:
    generic_filter = st.text_input(
        "Filter audit logs",
        placeholder="invoice_no ilike '%NS-2088%' and created_at >= '2026-08-20T00:00:00'",
        help="Examples: action = 'BUDGET_INCREASED', invoice_no ilike '%NS-2088%', matter_no = 'MAT-2088', request_id = '...'.",
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
    st.stop()

rows = []
for log in logs:
    matter = log.get("matter_label")
    if not matter:
        matter_no = log.get("matter_no")
        matter_name = log.get("matter_name")
        matter = " — ".join([str(x) for x in (matter_no, matter_name) if x]) or "—"

    rows.append(
        {
            "When": log.get("created_at"),
            "Request ID": log.get("request_id") or "Legacy / unavailable",
            "Action": log.get("action") or "—",
            "Invoice No.": log.get("invoice_no") or "No specific invoice",
            "Firm": log.get("firm_name") or "—",
            "Matter": matter,
            "User": log.get("user_name") or ("System" if log.get("user_id") in (-1, None) else f"User #{log.get('user_id')}") ,
            "Previous Value": log.get("previous_value") or "—",
            "Adjustment": log.get("adjustment_amount") or "—",
            "New Value": log.get("new_value") or "—",
            "Reason": log.get("reason") or "—",
            "Confirmed": "Yes" if log.get("confirmed") is True else ("No" if log.get("confirmed") is False else "—"),
            "Notes": log.get("notes") or "—",
        }
    )

df = pd.DataFrame(rows)
df["When"] = pd.to_datetime(df["When"], errors="coerce")
df = df.sort_values("When", ascending=False)

st.caption(
    "Internal database IDs are intentionally hidden here. The audit view shows business identifiers and names so an admin can identify the affected invoice, firm, and matter immediately."
)
st.dataframe(df, use_container_width=True, hide_index=True)