import streamlit as st

from utils.theme import badge, inject_base_css, kv_row, notice, page_header, sidebar_brand, status_badge
from utils.api_client import get_client, require_role, APIError
from utils.invoice_picker import pick_invoice

st.set_page_config(page_title="Review Decision | Konverge", page_icon="✅", layout="wide")
inject_base_css()
sidebar_brand()
require_role("admin", "editor")

client = get_client()

invoice = pick_invoice(label="Invoice to Decide")
if not invoice:
    st.stop()

try:
    review_inv = client.get_review_invoice(invoice["invoice_id"])
except APIError as e:
    review_inv = None
    st.warning(f"Couldn't load review-queue context (it may already be decided): {e.detail}")

page_header(7, "Review & Decision",
            "Full context for one invoice, and the decision that moves it out of the queue.",
            extra_badge=status_badge(invoice["status"]))

left, right = st.columns([2, 1])

with left:
    with st.container(border=True):
        st.markdown("#### Invoice Context")
        kv_row("Invoice", invoice.get("invoice_no") or f"#{invoice['invoice_id']}")
        kv_row("Amount", f"${invoice['total_amount']:,.2f}" if invoice.get("total_amount") is not None else "—")
        kv_row("Confidence", f"{invoice['confidence_score']:.0%}" if invoice.get("confidence_score") is not None else "—")
        kv_row("Budget Valid", "Yes" if invoice.get("budget_valid") else ("No" if invoice.get("budget_valid") is False else "—"))
        kv_row("Possible Duplicate", "Yes" if invoice.get("duplicate_flag") else "No")

        if review_inv and review_inv.get("review_reasons"):
            st.markdown("#### Why This Needs Review")
            for reason in review_inv["review_reasons"]:
                st.warning(reason)
        elif invoice["status"] not in ("under_review", "pending_review", "clarification_requested"):
            notice(f"This invoice's current status is **{invoice['status'].replace('_', ' ').title()}** — it may already be decided.")

with right:
    with st.container(border=True):
        st.markdown("#### Decision")
        action = st.radio("Action", ["Approve", "Reject", "Ask for Clarification"], horizontal=False)
        note_label = "Notes (optional)" if action == "Approve" else "Reason (required)"
        note_text = st.text_area(note_label)

        can_submit = action == "Approve" or bool(note_text.strip())
        if st.button("Submit Decision", type="primary", disabled=not can_submit):
            try:
                if action == "Approve":
                    client.approve(invoice["invoice_id"], notes=note_text or None)
                    st.success("Approved.")
                elif action == "Reject":
                    client.reject(invoice["invoice_id"], reason=note_text)
                    st.success("Rejected.")
                else:
                    client.clarify(invoice["invoice_id"], reason=note_text)
                    st.success("Clarification requested.")
                st.rerun()
            except APIError as e:
                st.error(e.detail)

        st.caption("Decision support only — this action is final once submitted and is recorded in the audit trail.")

st.markdown("---")
if st.button("← Back to Review Queue"):
    st.switch_page("pages/6_Review_Queue.py")
