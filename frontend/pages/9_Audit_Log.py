import math

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
    "Track the complete business history of invoices, budgets, firms and matters in one place. Latest activity appears first.",
)

client = get_client()

FILTER_DEFAULTS = {
    "audit_invoice_no": "",
    "audit_firm": "",
    "audit_matter_id": "",
    "audit_matter_name": "",
    "audit_request_id": "",
    "audit_general": "",
    "audit_action": "All actions",
    "audit_user": "All users",
    "audit_start_date": None,
    "audit_end_date": None,
    "audit_page": 1,
    "audit_page_size": 25,
}

for key, value in FILTER_DEFAULTS.items():
    st.session_state.setdefault(key, value)


def reset_audit_filters():
    # Explicit values are more reliable than pop() for already-instantiated
    # Streamlit widgets, and guarantee the visible controls clear as well.
    for key, value in FILTER_DEFAULTS.items():
        if key != "audit_page_size":
            st.session_state[key] = value


def first_page():
    st.session_state["audit_page"] = 1


try:
    # Only used to populate stable dropdown choices. The displayed rows below
    # are loaded page-by-page from the paginated API.
    option_logs = client.list_audit_logs(limit=1000) or []
except APIError:
    option_logs = []

actions = ["All actions"] + sorted({
    log.get("action") for log in option_logs if log.get("action")
})
users = ["All users"] + sorted({
    log.get("user_name") or ("System" if log.get("user_id") in (-1, None) else f"User #{log.get('user_id')}")
    for log in option_logs
})

# Protect persisted session values when the available options changed.
if st.session_state["audit_action"] not in actions:
    st.session_state["audit_action"] = "All actions"
if st.session_state["audit_user"] not in users:
    st.session_state["audit_user"] = "All users"

st.markdown("#### 🔎 Find audit activity")
with st.container(border=True):
    r1 = st.columns(3)
    r1[0].text_input("Invoice number", key="audit_invoice_no", placeholder="e.g. NS-2088-001", on_change=first_page)
    r1[1].text_input("Firm", key="audit_firm", placeholder="e.g. NorthStar", on_change=first_page)
    r1[2].text_input("Matter ID", key="audit_matter_id", placeholder="e.g. MAT-2088", on_change=first_page)

    r2 = st.columns(3)
    r2[0].text_input("Matter name", key="audit_matter_name", placeholder="e.g. Orion Systems v. Delta Labs", on_change=first_page)
    r2[1].text_input("Request ID", key="audit_request_id", placeholder="Paste request ID", on_change=first_page)
    r2[2].text_input("General Search", key="audit_general", placeholder="Search action, notes or business context", on_change=first_page)

r3 = st.columns([1.15, 1.15, 1.4, 0.65])
r3[0].selectbox("Action", actions, key="audit_action", on_change=first_page)
r3[1].selectbox("User", users, key="audit_user", on_change=first_page)
with r3[2]:
    d1, d2 = st.columns(2)
    d1.date_input("From", key="audit_start_date", value=None, on_change=first_page)
    d2.date_input("To", key="audit_end_date", value=None, on_change=first_page)
r3[3].button("Clear filters", use_container_width=True, on_click=reset_audit_filters)

page_size = st.selectbox(
    "Rows per page",
    [25, 30, 50],
    index=[25, 30, 50].index(st.session_state["audit_page_size"]),
    key="audit_page_size",
    on_change=first_page,
)

current_page = max(1, st.session_state["audit_page"])
offset = (current_page - 1) * page_size

try:
    page = client.list_audit_logs_page(
        invoice_no=st.session_state["audit_invoice_no"],
        firm_name=st.session_state["audit_firm"],
        matter_no=st.session_state["audit_matter_id"],
        matter_name=st.session_state["audit_matter_name"],
        request_id=st.session_state["audit_request_id"],
        action=None if st.session_state["audit_action"] == "All actions" else st.session_state["audit_action"],
        user_name=None if st.session_state["audit_user"] == "All users" else st.session_state["audit_user"],
        general=st.session_state["audit_general"],
        start_date=st.session_state["audit_start_date"],
        end_date=st.session_state["audit_end_date"],
        offset=offset,
        limit=page_size,
    )
except APIError as e:
    st.error(f"Couldn't load audit logs: {e.detail}")
    st.stop()

total = int(page.get("total", 0))
items = page.get("items", [])
total_pages = max(1, math.ceil(total / page_size))
if current_page > total_pages:
    st.session_state["audit_page"] = total_pages
    st.rerun()

rows = []
for log in items:
    matter = log.get("matter_label") or " — ".join(
        [str(x) for x in (log.get("matter_no"), log.get("matter_name")) if x]
    ) or "—"
    rows.append({
        "When": log.get("created_at"),
        "Request ID": log.get("request_id") or "Legacy / unavailable",
        "Action": log.get("action") or "—",
        "Invoice No.": log.get("invoice_no") or "No specific invoice",
        "Firm": log.get("firm_name") or "—",
        "Matter ID": log.get("matter_no") or "—",
        "Matter": matter,
        "User": log.get("user_name") or ("System" if log.get("user_id") in (-1, None) else f"User #{log.get('user_id')}"),
        "Previous Value": log.get("previous_value") or "—",
        "Adjustment": log.get("adjustment_amount") or "—",
        "New Value": log.get("new_value") or "—",
        "Reason": log.get("reason") or "—",
        "Confirmed": "Yes" if log.get("confirmed") is True else ("No" if log.get("confirmed") is False else "—"),
        "Notes": log.get("notes") or "—",
    })

df = pd.DataFrame(rows)
if not df.empty:
    df["When"] = pd.to_datetime(df["When"], errors="coerce")

start_row = offset + 1 if total else 0
end_row = min(offset + len(rows), total)
st.caption(
    f"Showing {start_row}-{end_row} of {total} matching audit event(s). Latest activity is shown first."
)

if df.empty:
    st.info("No audit entries match the selected filters.")
else:
    st.dataframe(df, use_container_width=True, hide_index=True)

nav_left, nav_mid, nav_right = st.columns([1, 2, 1])
with nav_left:
    if st.button("← Previous", disabled=current_page <= 1, use_container_width=True):
        st.session_state["audit_page"] = current_page - 1
        st.rerun()
with nav_mid:
    st.markdown(f"<div style='text-align:center; padding-top:0.45rem;'>Page <b>{current_page}</b> of <b>{total_pages}</b></div>", unsafe_allow_html=True)
with nav_right:
    if st.button("Next →", disabled=current_page >= total_pages or total == 0, use_container_width=True):
        st.session_state["audit_page"] = current_page + 1
        st.rerun()