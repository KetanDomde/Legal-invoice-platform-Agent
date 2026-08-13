import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.theme import inject_base_css, render_banner, kpi_tile, money, STATUS_COLORS, NAVY, ORANGE, BLUE, GREY
from utils.api_client import get_client, require_login, APIError

st.set_page_config(page_title="Dashboard | Konverge", page_icon="📊", layout="wide")
inject_base_css()
require_login()
render_banner("Dashboard", subtitle="Spend, budget utilization, and review pipeline at a glance.")

client = get_client()
try:
    invoices = client.list_invoices()
    matters = {m["matter_id"]: m for m in client.list_matters()}
    budgets = client.list_budgets()
    ledger = client.list_budget_ledger()
    alerts = client.list_alerts()
except APIError as e:
    st.error(f"Couldn't load dashboard data: {e.detail}")
    st.stop()

df = pd.DataFrame(invoices)

c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi_tile("Total invoices", str(len(df)))
with c2:
    kpi_tile("Total spend", money(df["total_amount"].sum()) if not df.empty else "$0.00")
with c3:
    approved_amt = df[df["status"] == "approved"]["total_amount"].sum() if not df.empty else 0
    kpi_tile("Approved spend", money(approved_amt))
with c4:
    pending = int((df["status"] == "under_review").sum()) if not df.empty else 0
    kpi_tile("Pending review", str(pending))

st.markdown("&nbsp;")
left, right = st.columns([1, 1.3])

with left:
    with st.container(border=True):
        st.markdown("##### Invoice status breakdown")
        if not df.empty:
            counts = df["status"].value_counts().reset_index()
            counts.columns = ["status", "count"]
            fig = px.pie(
                counts, names="status", values="count", hole=0.55,
                color="status", color_discrete_map=STATUS_COLORS,
            )
            fig.update_traces(textinfo="value+percent", textfont_size=13)
            fig.update_layout(showlegend=True, margin=dict(t=10, b=10, l=10, r=10), height=300,
                               legend=dict(orientation="h", y=-0.15))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No invoices yet.")

with right:
    with st.container(border=True):
        st.markdown("##### Spend by matter")
        if not df.empty:
            df["matter_name"] = df["matter_id"].map(lambda mid: matters.get(mid, {}).get("name", f"Matter {mid}"))
            by_matter = df.groupby("matter_name")["total_amount"].sum().reset_index().sort_values("total_amount")
            fig2 = go.Figure(go.Bar(
                x=by_matter["total_amount"], y=by_matter["matter_name"], orientation="h",
                marker_color=ORANGE, text=[money(v) for v in by_matter["total_amount"]], textposition="outside",
            ))
            fig2.update_layout(margin=dict(t=10, b=10, l=10, r=30), height=300,
                                xaxis_title=None, yaxis_title=None, plot_bgcolor="white")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No invoices yet.")

with st.container(border=True):
    st.markdown("##### Budget utilization by matter")
    if budgets:
        rows = []
        for b in budgets:
            used = sum(l["amount"] for l in ledger if l["budget_id"] == b["budget_id"])
            matter = matters.get(b["matter_id"], {})
            rows.append({
                "matter": matter.get("name", f"Matter {b['matter_id']}"),
                "allocated": b["allocated_amt"],
                "used": used,
                "pct": round(100 * used / b["allocated_amt"], 1) if b["allocated_amt"] else 0,
                "threshold": b["threshold_pct"],
            })
        budf = pd.DataFrame(rows)
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=budf["matter"], y=budf["allocated"], name="Allocated", marker_color="#E4E6F3"))
        fig3.add_trace(go.Bar(x=budf["matter"], y=budf["used"], name="Used", marker_color=NAVY))
        fig3.update_layout(barmode="overlay", height=280, margin=dict(t=10, b=10, l=10, r=10),
                            legend=dict(orientation="h", y=-0.2), plot_bgcolor="white")
        st.plotly_chart(fig3, use_container_width=True)
        st.dataframe(
            budf.rename(columns={"matter": "Matter", "allocated": "Allocated", "used": "Used",
                                  "pct": "% Used", "threshold": "Alert threshold %"}),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No budgets set up yet.")

if alerts:
    st.markdown("##### 🔔 Active alerts")
    for a in alerts:
        st.warning(a["message"])
