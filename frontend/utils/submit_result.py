"""
Shared renderer for a successful POST /invoices/submit response (the dict
built by _build_submit_response() in backend/app/api/invoices.py). Used by
both Home.py and pages/2_Invoices.py, and read from st.session_state so it
survives the rerun triggered after a submission (rather than flashing for
a single render pass).
"""
import streamlit as st

from utils.invoice_diff import render_invoice_diff

RESULT_KEY = "last_submit_result"
ERROR_KEY = "last_submit_error"


def render_submit_result(result: dict):
    invoice = result.get("extracted") or {}
    st.success(
        f"Invoice #{result.get('invoice_id', '—')} "
        f"({invoice.get('invoice_no', 'no number extracted')}) — "
        f"status: {result.get('final_status', 'submitted')}"
    )
    if result.get("warning"):
        st.warning(f"⚠️ {result['warning']}")

    m1, m2 = st.columns(2)
    conf = result.get("confidence_score")
    m1.metric("Confidence", f"{conf:.2f}" if conf is not None else "—")
    m2.metric("Status", result.get("final_status", "—"))

    st.write("**Extracted fields**")
    st.json(invoice)

    if invoice.get("line_items"):
        st.write("**Line items**")
        st.table(invoice["line_items"])

    if result.get("audit_trail"):
        with st.expander("Full audit trail"):
            for line in result["audit_trail"]:
                st.text(line)


def render_persisted_submit_result():
    """Renders the last submission result, if any, with a dismiss control.

    Call once near the top of a page, before the upload form.
    """
    result = st.session_state.get(RESULT_KEY)
    if not result:
        return
    with st.container(border=True):
        render_submit_result(result)
        if st.button("Dismiss", key="dismiss_submit_result"):
            del st.session_state[RESULT_KEY]
            st.rerun()
    st.markdown("&nbsp;")


def render_persisted_submit_error():
    """Renders the last duplicate-submission error (and its inv_changes
    diff), if any, with a dismiss control. Same rerun-survival need as
    render_persisted_submit_result — call once near the top of a page,
    before the upload form.
    """
    error = st.session_state.get(ERROR_KEY)
    if not error:
        return
    with st.container(border=True):
        st.error(f"🚫 {error['label']}: {error['detail']}")
        render_invoice_diff(error.get("inv_changes"))
        if st.button("Dismiss", key="dismiss_submit_error"):
            del st.session_state[ERROR_KEY]
            st.rerun()
    st.markdown("&nbsp;")

