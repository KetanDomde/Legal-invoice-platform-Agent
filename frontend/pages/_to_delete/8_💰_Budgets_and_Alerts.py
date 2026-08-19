import plotly.graph_objects as go
import streamlit as st

from utils.theme import NAVY, badge, inject_base_css, notice, page_header, sidebar_brand
from utils.api_client import get_client, require_login, APIError

st.set_page_config(page_title="Budgets & Alerts | Konverge", page_icon="💰", layout="wide")
inject_base_css()
sidebar_brand()
require_login()

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

page_header(8, "Budgets & Alerts",
            "Allocated budgets per matter, ledger history, and threshold alerts across every firm.",
            extra_badge=badge(f"{len(alerts)} active alert(s)", "orange" if alerts else "green"))

if user["role"] in ("admin", "editor"):
    with st.expander("➕ Add a budget"):
        if not matters:
            st.info("Create a matter first, on Admin Control.")
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

if budgets:
    rows = []
    for b in budgets:
        matter = matters.get(b["matter_id"], {})
        used = sum(l["amount"] for l in ledger if l["budget_id"] == b["budget_id"])
        rows.append({
            "matter": matter.get("name", f"Matter {b['matter_id']}"),
            "allocated": b["allocated_amt"],
            "used": used,
        })
    with st.container(border=True):
        st.markdown("##### Budget utilization by matter")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[r["matter"] for r in rows], y=[r["allocated"] for r in rows], name="Allocated", marker_color="#E4E6F3"))
        fig.add_trace(go.Bar(x=[r["matter"] for r in rows], y=[r["used"] for r in rows], name="Used", marker_color=NAVY))
        fig.update_layout(barmode="overlay", height=280, margin=dict(t=10, b=10, l=10, r=10),
                           legend=dict(orientation="h", y=-0.2), plot_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)

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
            used_num = f"{used:,.2f}"
            allocated_num = f"{b['allocated_amt']:,.2f}"
            st.progress(min(pct / 100, 1.0), text=f"${used_num} of {allocated_num} used ({pct:.0f}%)")
            if pct >= b["threshold_pct"]:
                notice(f"Over the {b['threshold_pct']:.0f}% alert threshold — recommend Clarify before Approve on new invoices for this matter.")
        with c2:
            entries = [l for l in ledger if l["budget_id"] == b["budget_id"]]
            st.caption(f"{len(entries)} ledger entr{'y' if len(entries) == 1 else 'ies'}")
            for e in entries[:4]:
                st.caption(f"• Invoice #{e['invoice_id']} — ${e['amount']:,.2f} ({e['entry_type']})")

if alerts:
    st.markdown("##### 🔔 All Alerts")
    for a in alerts:
        st.warning(a["message"])
else:
    st.caption("No alerts fired yet.")
