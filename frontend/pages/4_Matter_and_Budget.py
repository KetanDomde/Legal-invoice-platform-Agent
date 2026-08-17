import streamlit as st

from utils.theme import badge, inject_base_css, kv_row, notice, page_header, sidebar_brand
from utils.api_client import get_client, require_login, APIError
from utils.invoice_picker import pick_invoice

st.set_page_config(page_title="Matter & Budget Context | Konverge", page_icon="🏛️", layout="wide")
inject_base_css()
sidebar_brand()
require_login()

client = get_client()

invoice = pick_invoice(label="Open Invoice")
if not invoice:
    st.stop()

try:
    matters = {m["matter_id"]: m for m in client.list_matters()}
    firms = {f["firm_id"]: f for f in client.list_firms()}
    budgets = client.list_budgets()
    ledger = client.list_budget_ledger()
    alerts = client.list_alerts()
except APIError as e:
    st.error(f"Couldn't load matter/budget data: {e.detail}")
    st.stop()

matter = matters.get(invoice["matter_id"])
if not matter:
    st.error(f"Matter {invoice['matter_id']} not found.")
    st.stop()

firm = firms.get(matter["firm_id"], {})
budget = next((b for b in budgets if b["matter_id"] == matter["matter_id"]), None)

page_header(4, "Matter & Budget Context",
            f"Full spend context for {matter['name']} — the matter this invoice bills against.",
            extra_badge=badge("Budget Set", "green") if budget else badge("No Budget", "gray"))

left, right = st.columns([2, 1])

with left:
    with st.container(border=True):
        st.markdown("#### Matter Context")
        kv_row("Matter", matter["name"])
        kv_row("Firm", firm.get("name", f"Firm {matter['firm_id']}"))
        kv_row("Owner", matter["owner"])
        kv_row("Matter Status", matter["status"].title())

        st.markdown("#### Budget Ledger Evidence")
        if budget:
            entries = [l for l in ledger if l["budget_id"] == budget["budget_id"]]
            if entries:
                st.dataframe(
                    [{"Ledger ID": e["ledger_id"], "Invoice": f"#{e['invoice_id']}", "Amount": f"${e['amount']:,.2f}",
                      "Entry Type": e["entry_type"].replace("_", " ").title(), "When": e["created_at"]} for e in entries],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.caption("No ledger entries posted for this budget yet.")
        else:
            st.caption("This matter has no budget configured — set one up on the Budgets & Alerts page.")

with right:
    with st.container(border=True):
        st.markdown("#### Budget Utilization")
        if budget:
            used = sum(l["amount"] for l in ledger if l["budget_id"] == budget["budget_id"])
            allocated = budget["allocated_amt"]
            pct = (used / allocated * 100) if allocated else 0
            used_num = f"{used:,.2f}"
            allocated_num = f"{allocated:,.2f}"
            st.progress(min(pct / 100, 1.0), text=f"${used_num} of {allocated_num} used ({pct:.0f}%)")
            kv_row("Alert Threshold", f"{budget['threshold_pct']:.0f}%")
            if pct >= budget["threshold_pct"]:
                notice(f"Over the {budget['threshold_pct']:.0f}% alert threshold — recommend Clarify before Approve on new invoices for this matter.")
            else:
                notice("Within budget threshold.", success=True)
        else:
            st.caption("No budget to evaluate.")

        matter_alerts = [a for a in alerts if budget and a["budget_id"] == budget["budget_id"]]
        if matter_alerts:
            st.markdown("#### Alerts for This Matter")
            for a in matter_alerts:
                st.warning(a["message"])

st.markdown("---")
if st.button("Continue to Validation & Duplicate Check →", type="primary"):
    st.switch_page("pages/5_Validation_Check.py")
