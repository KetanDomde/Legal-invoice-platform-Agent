import streamlit as st

from utils.theme import inject_base_css, render_banner, money
from utils.api_client import get_client, require_login, APIError

st.set_page_config(page_title="Budgets & Alerts | Konverge", page_icon="💰", layout="wide")
inject_base_css()
require_login()
render_banner("Budgets & Alerts", subtitle="Allocated budgets per matter, ledger history, and threshold alerts.")

client = get_client()
user = st.session_state["user"]

try:
    budgets = client.list_budgets()
    matters = {m["matter_id"]: m for m in client.list_matters()}
    ledger = client.list_budget_ledger()
    alerts = client.list_alerts()
except APIError as e:
    st.error(f"Couldn't load budget data: {e.detail}")
    st.stop()

if user["role"] in ("admin", "editor"):
    with st.expander("➕ Add a budget"):
        if not matters:
            st.info("Create a matter first.")
        else:
            matter_lookup = {m["name"]: mid for mid, m in matters.items()}
            with st.form("new_budget", clear_on_submit=True):
                matter_label = st.selectbox("Matter", list(matter_lookup.keys()))
                allocated = st.number_input("Allocated amount ($)", min_value=1.0, step=1000.0, value=10000.0)
                threshold = st.slider("Alert threshold (%)", 0, 100, 80)
                if st.form_submit_button("Create budget", type="primary"):
                    try:
                        client.create_budget(matter_id=matter_lookup[matter_label],
                                              allocated_amt=allocated, threshold_pct=threshold)
                        st.success("Budget created.")
                        st.rerun()
                    except APIError as e:
                        st.error(e.detail)

st.markdown("&nbsp;")

for b in budgets:
    matter = matters.get(b["matter_id"], {})
    matter_name = matter.get("name", f"Matter {b['matter_id']}")
    used = sum(l["amount"] for l in ledger if l["budget_id"] == b["budget_id"])
    pct = (used / b["allocated_amt"] * 100) if b["allocated_amt"] else 0
    with st.container(border=True):
        c1, c2 = st.columns([2, 1.4])
        with c1:
            st.markdown(f"**{matter_name}**")
            # Only one literal "$" in this string, on purpose: Streamlit's markdown
            # renders any PAIR of "$" as LaTeX math, which mangles "$X of $Y" into
            # squished italic text (backslash-escaping the "$" doesn't stop it either).
            used_num = f"{used:,.2f}"
            allocated_num = f"{b['allocated_amt']:,.2f}"
            st.progress(min(pct / 100, 1.0), text=f"${used_num} of {allocated_num} used ({pct:.0f}%)")
            if pct >= b["threshold_pct"]:
                st.warning(f"Over the {b['threshold_pct']:.0f}% alert threshold.")
        with c2:
            entries = [l for l in ledger if l["budget_id"] == b["budget_id"]]
            st.caption(f"{len(entries)} ledger entr{'y' if len(entries) == 1 else 'ies'}")
            for e in entries[:4]:
                st.caption(f"• Invoice #{e['invoice_id']} — {money(e['amount'])} ({e['entry_type']})")

if alerts:
    st.markdown("##### 🔔 Alerts")
    for a in alerts:
        st.warning(a["message"])
else:
    st.caption("No alerts fired yet.")
