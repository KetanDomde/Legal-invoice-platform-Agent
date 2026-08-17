import streamlit as st

from utils.theme import inject_base_css, kv_row, notice, page_header, sidebar_brand
from utils.api_client import get_client, require_login, APIError

st.set_page_config(page_title="New Intake | Konverge", page_icon="📝", layout="wide")
inject_base_css()
sidebar_brand()
require_login()

page_header(2, "New Intake & Extraction",
            "Submit an invoice PDF to the real extraction/validation pipeline and see exactly what came back — "
            "extracted fields, confidence, duplicate check, and the full audit trail for this submission.")

client = get_client()
user = st.session_state["user"]

if user["role"] not in ("admin", "editor"):
    st.info("Viewer role: read-only. Ask an Editor or Admin to submit a new invoice.")
    st.stop()

try:
    matters = client.list_matters()
except APIError as e:
    st.error(f"Couldn't load matters: {e.detail}")
    st.stop()

if not matters:
    st.info("No matters available yet — create one on the **Admin Control** page first.")
    st.stop()

with st.container(border=True):
    st.markdown("#### Submit an Invoice")
    matter_lookup = {f"{m['name']} (Matter #{m['matter_id']})": m["matter_id"] for m in matters}
    c1, c2 = st.columns([2, 1])
    with c1:
        matter_label = st.selectbox("Matter *", list(matter_lookup.keys()))
    with c2:
        matter_name_hint = st.text_input("Matter name (optional override)", placeholder="only if extraction can't find one")
    uploaded_file = st.file_uploader("Invoice file (PDF or TXT) *", type=["pdf", "txt"])

    can_submit = uploaded_file is not None
    if st.button("Submit Intake", type="primary", disabled=not can_submit):
        matter_id = matter_lookup[matter_label]
        with st.spinner("Extracting, validating, and persisting..."):
            try:
                result = client.submit_invoice(matter_id, uploaded_file, matter_name=matter_name_hint or None)
            except APIError as e:
                if e.status_code == 409:
                    st.error(f"🚫 Duplicate: {e.detail}")
                elif e.status_code == 422:
                    st.error(f"Invalid request: {e.detail}")
                elif e.status_code == 404:
                    st.error(f"{e.detail}")
                else:
                    st.error(f"API error {e.status_code}: {e.detail}")
                result = None
        if result is not None:
            st.session_state["_last_intake_result"] = result
            st.session_state["selected_invoice_id"] = result["invoice_id"]
            st.rerun()

result = st.session_state.pop("_last_intake_result", None)
if result:
    extracted = result.get("extracted") or {}
    status_ok = result.get("final_status") not in (None,) and not result.get("is_duplicate")

    left, right = st.columns([2, 1])

    with left:
        with st.container(border=True):
            st.markdown("#### Intake Result")
            kv_row("Invoice ID", f"#{result['invoice_id']}")
            kv_row("Status", (result.get("final_status") or "—").replace("_", " ").title())
            kv_row("Invoice No.", extracted.get("invoice_no", "—"))
            kv_row("Invoice Date", extracted.get("invoice_date") or "—")
            kv_row("Total Amount", f"${extracted['total_amount']:,.2f}" if extracted.get("total_amount") is not None else "—")

            st.markdown("#### Line Items")
            line_items = extracted.get("line_items") or []
            if line_items:
                st.dataframe(line_items, use_container_width=True, hide_index=True)
            else:
                st.caption("No line items extracted.")

    with right:
        with st.container(border=True):
            st.markdown("#### Validation Check")
            conf = result.get("confidence_score")
            st.metric("Extraction confidence", f"{conf:.0%}" if conf is not None else "—")
            if result.get("is_duplicate"):
                notice(f"⚠️ Flagged as a duplicate — {result.get('warning', 'routed to human review instead of auto-approve.')}")
            elif result.get("validation_passed") is False:
                notice(f"Validation flagged: {result.get('validation_reason') or 'see review queue for details.'}")
            else:
                notice("All checks passed — no remediation required.", success=True)

    with st.container(border=True):
        st.markdown("#### Audit Trail for This Submission")
        for line in result.get("audit_trail") or []:
            st.text(line)

    if st.button("Open in Invoice Workspace →", type="primary"):
        st.switch_page("pages/3_🗂️_Invoice_Workspace.py")
