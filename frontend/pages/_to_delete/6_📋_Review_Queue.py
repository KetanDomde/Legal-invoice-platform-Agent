import streamlit as st

from utils.theme import badge, inject_base_css, page_header, sidebar_brand, status_badge
from utils.api_client import get_client, require_role, APIError

st.set_page_config(page_title="Review Queue | Konverge", page_icon="📋", layout="wide")
inject_base_css()
sidebar_brand()
require_role("admin", "editor")

client = get_client()

try:
    queue = client.review_queue()
except APIError as e:
    st.error(f"Couldn't load the review queue: {e.detail}")
    st.stop()

page_header(6, "Review Queue",
            "Invoices held for human review — low confidence, budget conflicts, or possible duplicates.",
            extra_badge=badge(f"{len(queue)} waiting", "orange" if queue else "green"))

if not queue:
    st.success("Nothing waiting for review right now. 🎉")
    st.stop()

for inv in queue:
    with st.container(border=True):
        c1, c2 = st.columns([2.4, 1])
        with c1:
            st.markdown(f"#### {inv['invoice_no']}  &nbsp; {status_badge(inv['status'])}", unsafe_allow_html=True)
            confidence_str = f"{inv['confidence_score']:.0%}" if inv["confidence_score"] is not None else "—"
            budget_str = "Yes" if inv["budget_valid"] else ("No" if inv["budget_valid"] is False else "—")
            duplicate_str = "Yes" if inv["duplicate_flag"] else "No"
            st.markdown(
                f"**Amount:** ${inv['total_amount']:,.2f} &nbsp;·&nbsp; "
                f"**Confidence:** {confidence_str} &nbsp;·&nbsp; "
                f"**Budget OK:** {budget_str} &nbsp;·&nbsp; "
                f"**Possible duplicate:** {duplicate_str}"
            )
            if inv.get("review_reasons"):
                st.warning(" · ".join(inv["review_reasons"]))
        with c2:
            if st.button("Open Decision →", key=f"open_{inv['invoice_id']}", use_container_width=True, type="primary"):
                st.session_state["selected_invoice_id"] = inv["invoice_id"]
                st.switch_page("pages/7_✅_Review_Decision.py")
            with st.popover("✅ Quick approve", use_container_width=True):
                notes = st.text_area("Notes (optional)", key=f"appr_notes_{inv['invoice_id']}")
                if st.button("Confirm approve", key=f"appr_btn_{inv['invoice_id']}", type="primary"):
                    try:
                        client.approve(inv["invoice_id"], notes=notes or None)
                        st.success("Approved.")
                        st.rerun()
                    except APIError as e:
                        st.error(e.detail)
            with st.popover("❌ Quick reject", use_container_width=True):
                reason = st.text_area("Reason (required)", key=f"rej_reason_{inv['invoice_id']}")
                if st.button("Confirm reject", key=f"rej_btn_{inv['invoice_id']}"):
                    if not reason:
                        st.error("A reason is required to reject.")
                    else:
                        try:
                            client.reject(inv["invoice_id"], reason=reason)
                            st.success("Rejected.")
                            st.rerun()
                        except APIError as e:
                            st.error(e.detail)
