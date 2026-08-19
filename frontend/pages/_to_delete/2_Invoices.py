import pandas as pd
import streamlit as st

from utils.theme import inject_base_css, render_banner, status_badge, money
from utils.api_client import get_client, require_login, APIError
from utils.submit_result import render_persisted_submit_result, render_persisted_submit_error, RESULT_KEY, ERROR_KEY

st.set_page_config(page_title="Invoices | Konverge", page_icon="🧾", layout="wide")
inject_base_css()
require_login()
render_banner("Invoices", subtitle="Upload invoices for automatic extraction, validation & review.")

client = get_client()
user = st.session_state["user"]

try:
    matters = client.list_matters()
except APIError as e:
    st.error(f"Couldn't load matters: {e.detail}")
    st.stop()

# --- Upload -----------------------------------------------------------
if user["role"] in ("admin", "editor"):
    render_persisted_submit_result()
    render_persisted_submit_error()

    with st.expander("📤 Upload invoice for processing", expanded=False):
        uploaded_file = st.file_uploader("Invoice PDF", type=["pdf"])

        can_submit = uploaded_file is not None
        if st.button("Submit invoice", type="primary", disabled=not can_submit):
            with st.spinner("Extracting and validating..."):
                try:
                    result = client.submit_invoice(uploaded_file)
                except APIError as e:
                    if e.status_code == 409:
                        st.session_state[ERROR_KEY] = {
                            "label": "Duplicate invoice",
                            "detail": e.detail,
                            "inv_changes": getattr(e, "inv_changes", None),
                        }
                    elif e.status_code == 422:
                        st.error(f"Extraction/validation failed: {e.detail}")
                    else:
                        st.error(f"API error {e.status_code}: {e.detail}")
                    result = None

            if result is not None:
                st.session_state[RESULT_KEY] = result
                st.rerun()
            elif ERROR_KEY in st.session_state:
                st.rerun()
else:
    st.caption("Viewer role: read-only. Ask an Editor or Admin to upload a new invoice.")

st.markdown("&nbsp;")

# --- List ---------------------------------------------------------------
try:
    invoices = client.list_invoices()
except APIError as e:
    st.error(f"Couldn't load invoices: {e.detail}")
    st.stop()

matter_names = {m["matter_id"]: m["name"] for m in matters}

if not invoices:
    st.info("No invoices yet.")
else:
    df = pd.DataFrame(invoices)
    df["matter"] = df["matter_id"].map(matter_names)
    st.markdown("##### All invoices")
    for _, row in df.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 2, 1.4, 1.4])
            with c1:
                display_no = row.get("invoice_no") or f"Invoice #{row['invoice_id']}"
                st.markdown(f"**{display_no}**")
                st.caption(row["matter"] or f"Matter {row['matter_id']}")
            with c2:
                if pd.notna(row.get("total_amount")):
                    st.markdown(money(row["total_amount"]))
                else:
                    st.markdown("—")
                has_confidence = pd.notna(row.get("confidence_score"))
                st.caption(f"Confidence: {row['confidence_score']:.0%}" if has_confidence else "Not yet scored")
            with c3:
                st.markdown(status_badge(row["status"]), unsafe_allow_html=True)
            with c4:
                if row.get("review_reasons"):
                    st.caption("⚠️ " + "; ".join(row["review_reasons"]))