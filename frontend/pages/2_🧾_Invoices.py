from datetime import date

import pandas as pd
import streamlit as st

from utils.theme import inject_base_css, render_banner, status_badge, money
from utils.api_client import get_client, require_login, APIError

st.set_page_config(page_title="Invoices | Konverge", page_icon="🧾", layout="wide")
inject_base_css()
require_login()
render_banner("Invoices", subtitle="Submit new invoices and track their validation & review status.")

client = get_client()
user = st.session_state["user"]

try:
    matters = client.list_matters()
except APIError as e:
    st.error(f"Couldn't load matters: {e.detail}")
    st.stop()

if user["role"] in ("admin", "editor"):
    with st.expander("➕ Submit a new invoice", expanded=False):
        if not matters:
            st.info("No matters available yet — create one on the Firms & Matters page first.")
        else:
            matter_lookup = {f"{m['name']} (Matter #{m['matter_id']})": m for m in matters}
            with st.form("new_invoice_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    matter_label = st.selectbox("Matter", list(matter_lookup.keys()))
                    invoice_no = st.text_input("Invoice number", placeholder="INV-1006")
                with col2:
                    invoice_date = st.date_input("Invoice date", value=date.today())
                    total_amount = st.number_input("Total amount ($)", min_value=0.01, step=100.0)
                submitted = st.form_submit_button("Submit invoice", type="primary")
            if submitted:
                matter = matter_lookup[matter_label]
                if not invoice_no:
                    st.error("Invoice number is required.")
                else:
                    try:
                        client.create_invoice(
                            matter_id=matter["matter_id"], firm_id=matter["firm_id"],
                            invoice_no=invoice_no, total_amount=total_amount, invoice_date=invoice_date,
                        )
                        st.success(f"Invoice {invoice_no} submitted.")
                        st.rerun()
                    except APIError as e:
                        st.error(f"Couldn't submit invoice: {e.detail}")
    st.caption(
        "Note: structured entry only for now — the OCR/PDF-extraction endpoint (Bhushan's module) "
        "isn't wired into the API yet, so this form mirrors the fields the backend currently accepts."
    )
else:
    st.caption("Viewer role: read-only. Ask an Editor or Admin to submit a new invoice.")

st.markdown("&nbsp;")

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
                st.markdown(f"**{row['invoice_no']}**")
                st.caption(row["matter"] or f"Matter {row['matter_id']}")
            with c2:
                st.markdown(money(row["total_amount"]))
                has_confidence = pd.notna(row["confidence_score"])
                st.caption(f"Confidence: {row['confidence_score']:.0%}" if has_confidence else "Not yet scored")
            with c3:
                st.markdown(status_badge(row["status"]), unsafe_allow_html=True)
            with c4:
                if row.get("review_reasons"):
                    st.caption("⚠️ " + "; ".join(row["review_reasons"]))
