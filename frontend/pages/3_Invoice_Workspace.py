import streamlit as st

from utils.theme import inject_base_css, kv_row, page_header, sidebar_brand, status_badge, timeline
from utils.api_client import get_client, require_login, APIError
from utils.invoice_picker import pick_invoice

st.set_page_config(page_title="Invoice Workspace | Konverge", page_icon="🗂️", layout="wide")
inject_base_css()
sidebar_brand()
require_login()

client = get_client()
user = st.session_state["user"]


# ---------------------------------------------------------------------------
# Invoice Search / Filters
# ---------------------------------------------------------------------------

st.markdown("### Find Invoice")

try:
    firms_list = client.list_firms()
    matters_list = client.list_matters()
except APIError as e:
    st.error(f"Couldn't load invoice filters: {e.detail}")
    st.stop()


# Firm filter
firm_options = {
    "All Firms": None
}

for firm in firms_list:
    firm_options[
        f"{firm['name']} (ID: {firm['firm_id']})"
    ] = firm["firm_id"]


selected_firm_label = st.selectbox(
    "Search by Firm / Vendor",
    list(firm_options.keys()),
)

selected_firm_id = firm_options[selected_firm_label]


# Matter filter
matter_options = {
    "All Matters": None
}

# If a firm is selected, only show matters belonging to that firm
for matter in matters_list:

    if (
        selected_firm_id is not None
        and matter["firm_id"] != selected_firm_id
    ):
        continue

    matter_options[
        f"{matter['name']} (ID: {matter['matter_id']})"
    ] = matter["matter_id"]


selected_matter_label = st.selectbox(
    "Search by Matter",
    list(matter_options.keys()),
)

selected_matter_id = matter_options[selected_matter_label]


# ---------------------------------------------------------------------------
# Invoice picker
# ---------------------------------------------------------------------------

invoice = pick_invoice(
    label="Open Invoice",
    matter_id=selected_matter_id,
    firm_id=selected_firm_id,
)

if not invoice:
    st.stop()
    


try:
    matters = {m["matter_id"]: m for m in client.list_matters()}
    firms = {f["firm_id"]: f for f in client.list_firms()}
    line_items = client.list_line_items(invoice_id=invoice["invoice_id"]) or []
except APIError as e:
    st.error(f"Couldn't load workspace data: {e.detail}")
    st.stop()

matter = matters.get(invoice["matter_id"], {})
firm = firms.get(invoice["firm_id"], {})

left, right = st.columns([2, 1])

with left:
    with st.container(border=True):

        st.markdown("#### Invoice Header")

        kv_row(
            "Invoice ID",
            f"#{invoice['invoice_id']}"
        )

        kv_row(
            "Invoice No.",
            invoice.get("invoice_no") or "—"
        )

        kv_row(
            "Vendor / Firm",
            firm.get(
                "name",
                f"Firm {invoice['firm_id']}"
            )
        )

        kv_row(
            "Matter",
            matter.get(
                "name",
                f"Matter {invoice['matter_id']}"
            )
        )

        kv_row(
            "Invoice Date",
            invoice.get("invoice_date") or "—"
        )

        kv_row(
            "Total Amount",
            (
                f"${invoice['total_amount']:,.2f}"
                if invoice.get("total_amount") is not None
                else "—"
            )
        )

        kv_row(
            "Current Status",
            status_badge(invoice["status"])
        )
        




page_header(3, "Invoice Workspace / Invoice Detail",
            "Central invoice view — status, line items, artifacts, and audit trail, all live from the database.",
            extra_badge=status_badge(invoice["status"]))

TIMELINE_STEPS = ["Submitted", "Extracted & Validated", "Under Review", "Decision"]


def _step_state(idx: int, status: str):
    order = ["submitted", "pending_review", "under_review", "clarification_required", "approved", "rejected"]
    if status in ("approved", "rejected"):
        reached = 4
    elif status in ("under_review", "pending_review", "clarification_required"):
        reached = 3
    else:
        reached = 2  # any recorded status beyond raw "submitted" means extraction ran
    if status == "submitted":
        reached = 1

    if idx + 1 < reached:
        return "done"
    if idx + 1 == reached:
        return "rejected" if status == "rejected" and idx == 3 else "active"
    return "pending"


left, right = st.columns([2, 1])

with left:
    with st.container(border=True):
        st.markdown("#### Invoice Header")

        kv_row("Invoice ID", f"#{invoice['invoice_id']}")
        kv_row("Invoice No.", invoice.get("invoice_no") or "—")

        # Vendor / Law Firm that owns the invoice
        kv_row(
            "Vendor / Firm",
            firm.get("name", f"Firm {invoice['firm_id']}")
        )

        kv_row(
            "Matter",
            matter.get("name", f"Matter {invoice['matter_id']}")
        )

        kv_row("Invoice Date", invoice.get("invoice_date") or "—")
        kv_row(
            "Total Amount",
            f"${invoice['total_amount']:,.2f}"
            if invoice.get("total_amount") is not None
            else "—"
        )
        kv_row("Current Status", status_badge(invoice["status"]))
        

        st.markdown("#### Line Items")
        if line_items:
            st.dataframe(
                [{"Timekeeper": li.get("timekeeper") or "—", "Hours": li.get("hours"), "Rate": li.get("rate"),
                  "Amount": f"${li['amount']:,.2f}"} for li in line_items],
                use_container_width=True, hide_index=True,
            )
        else:
            st.caption("No line items recorded.")

        st.markdown("#### Status Timeline")
        timeline([(label, _step_state(i, invoice["status"])) for i, label in enumerate(TIMELINE_STEPS)])

with right:
    with st.container(border=True):
        st.markdown("#### Artifacts")
        st.markdown(f"- Extracted Fields &nbsp;{status_badge('approved') if invoice.get('invoice_no') else status_badge('submitted')}", unsafe_allow_html=True)
        st.markdown(f"- Line Items ({len(line_items)}) &nbsp;{status_badge('approved') if line_items else status_badge('submitted')}", unsafe_allow_html=True)
        st.markdown(f"- Validation Result &nbsp;{status_badge(invoice['validation_status']) if invoice.get('validation_status') else status_badge('submitted')}", unsafe_allow_html=True)

        st.markdown("#### Quick Actions")
        if st.button("Matter & Budget Context →", use_container_width=True):
            st.switch_page("pages/4_Matter_and_Budget.py")
        if st.button("Validation & Duplicate Check →", use_container_width=True):
            st.switch_page("pages/5_Validation_Check.py")
        if user["role"] in ("admin", "editor") and invoice["status"] in ("under_review", "pending_review", "clarification_required"):
            if st.button("Review Decision →", use_container_width=True, type="primary"):
                st.switch_page("pages/7_Review_Decision.py")

        if user["role"] in ("admin", "editor"):
            with st.expander("🔁 Re-process from a corrected file"):
                st.caption("Re-runs extraction against a new file and updates this invoice. Always goes back to Pending Review — never silently re-auto-approves.")
                new_file = st.file_uploader("Corrected file", type=["pdf", "txt"], key="reprocess_file")
                if st.button("Re-process", disabled=new_file is None):
                    try:
                        res = client.update_invoice_file(invoice["invoice_id"], invoice["matter_id"], new_file)
                        st.success(res.get("message", "Updated."))
                        st.rerun()
                    except APIError as e:
                        st.error(e.detail)

st.markdown("#### Audit Trail")
try:
    logs = client.list_audit_logs(invoice_id=invoice["invoice_id"])
except APIError as e:
    logs = []
    st.error(f"Couldn't load audit trail: {e.detail}")

if logs:
    import pandas as pd
    df = pd.DataFrame(logs).sort_values("created_at", ascending=False)
    st.dataframe(
        df.rename(columns={"audit_id": "ID", "user_id": "User", "action": "Action", "notes": "Notes", "created_at": "When"})
          [["ID", "User", "Action", "Notes", "When"]],
        use_container_width=True, hide_index=True,
    )
else:
    st.caption("No audit events for this invoice yet.")
