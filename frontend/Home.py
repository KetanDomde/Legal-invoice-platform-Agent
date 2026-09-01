import html
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.theme import (
    STATUS_COLORS,
    badge,
    inject_base_css,
    kpi_tile,
    page_header,
    render_banner,
    role_badge,
    sidebar_brand,
)
from utils.api_client import get_client, APIError, DEFAULT_BASE_URL


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Konverge | Legal Invoice Platform",
    page_icon="📥",
    layout="wide",
)

inject_base_css()
sidebar_brand()

if "base_url" not in st.session_state:
    st.session_state["base_url"] = DEFAULT_BASE_URL


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.caption("Agent Workbench")

    with st.expander("⚙️ Connection", expanded=False):
        st.session_state["base_url"] = st.text_input(
            "API base URL",
            value=st.session_state["base_url"],
            help="Point this at your FastAPI server. Defaults to your local backend.",
        )

        client_probe = get_client()
        try:
            client_probe.health()
            st.success("API connected")
        except APIError as e:
            st.error(f"API unreachable: {e.detail}")

    if st.session_state.get("user"):
        u = st.session_state["user"]

        st.markdown(
            f"""
            <div class="kv-sidebar-card">
                <b>{u['name']}</b><br/>
                {role_badge(u['role'])}
                <div style="font-size:0.8rem;margin-top:4px;">{u['email']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("Log out", use_container_width=True):
            st.session_state.pop("token", None)
            st.session_state.pop("user", None)
            st.rerun()



st.markdown(
    """
    <style>
    .budget-alert-panel {
        max-height: 520px;
        overflow-y: auto;
        padding: 2px 4px 4px 2px;
    }
    .budget-alert-card {
        border: 1px solid #d9d9e2;
        border-radius: 10px;
        padding: 12px 13px;
        margin: 0 0 10px 0;
        background: #ffffff;
        font-family: inherit;
        line-height: 1.5;
        overflow-wrap: anywhere;
    }
    .budget-alert-card.over-budget {
        border-left: 5px solid #dc2626;
        background: #fff7f7;
    }
    .budget-alert-card.threshold {
        border-left: 5px solid #f59e0b;
        background: #fffbeb;
    }
    .budget-alert-title {
        font-size: 0.95rem;
        font-weight: 700;
        line-height: 1.35;
        margin-bottom: 8px;
    }
    .budget-alert-card.over-budget .budget-alert-title {
        color: #b91c1c;
    }
    .budget-alert-card.threshold .budget-alert-title {
        color: #92400e;
    }
    .budget-alert-meta {
        font-size: 0.82rem;
        line-height: 1.5;
        color: #64748b;
        margin: 3px 0;
    }
    .budget-alert-message {
        font-size: 0.86rem;
        line-height: 1.55;
        color: #1f2937;
        margin-top: 8px;
    }
    .budget-alert-footer {
        font-size: 0.76rem;
        color: #64748b;
        margin-top: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _clean_alert_text(value) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[*_`]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _alert_kind(alert: dict) -> str:
    # Prefer the backend's explicit classification when available.
    # Message matching remains as a backward-compatible fallback.
    explicit = str(
        alert.get("type")
        or alert.get("alert_type")
        or alert.get("budget_result")
        or ""
    ).strip().lower().replace("-", "_")

    if explicit in {
        "over_budget",
        "over_budget_detected",
        "budget_overrun",
        "overbudget",
    }:
        return "over-budget"

    if explicit in {
        "threshold_reached",
        "budget_threshold_reached",
        "budget_threshold",
    }:
        return "threshold"

    value = " ".join(
        str(alert.get(k) or "")
        for k in ("type", "alert_type", "budget_result", "message")
    ).lower()

    if any(
        x in value
        for x in ("over_budget", "over budget", "overrun", "exceed")
    ):
        return "over-budget"

    return "threshold"


def render_budget_alert(alert: dict) -> None:
    kind = _alert_kind(alert)
    title = (
        "⚠️ Over Budget Detected"
        if kind == "over-budget"
        else "⚠️ Budget Threshold Reached"
    )

    firm = _clean_alert_text(alert.get("firm_name")) or "—"
    matter_no = _clean_alert_text(alert.get("matter_no"))
    matter_name = _clean_alert_text(alert.get("matter_name")) or "—"
    invoice_no = _clean_alert_text(alert.get("invoice_no"))
    message = _clean_alert_text(alert.get("message")) or "Budget attention required."

    matter = f"{matter_no} — {matter_name}" if matter_no else matter_name

    utilization = alert.get("utilization_pct")
    threshold = alert.get("threshold_pct")

    utilization_text = (
        f"{float(utilization):.1f}%"
        if utilization is not None else "—"
    )
    threshold_text = (
        f"{float(threshold):.1f}%"
        if threshold is not None else "—"
    )

    st.markdown(
        f"""
        <div class="budget-alert-card {kind}">
            <div class="budget-alert-title">{title}</div>
            <div class="budget-alert-meta">🏢 <b>Firm:</b> {html.escape(firm)}</div>
            <div class="budget-alert-meta">📁 <b>Matter:</b> {html.escape(matter)}</div>
            <div class="budget-alert-meta">📄 <b>Invoice:</b> {html.escape(invoice_no or "—")}</div>
            <div class="budget-alert-message">{html.escape(message)}</div>
            <div class="budget-alert-footer">
                Utilization: <b>{utilization_text}</b>
                &nbsp;·&nbsp;
                Threshold: <b>{threshold_text}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Header / Login
# ---------------------------------------------------------------------------
render_banner(
    "Legal Invoice Tracking & Spend Management",
    subtitle="AI-assisted invoice review, budget tracking, and audit trail — built for outside-counsel spend.",
)

if not st.session_state.get("token"):
    if st.session_state.pop("session_expired", False):
        st.info("Your session has expired. Please log in again.")

    left, mid, right = st.columns([1, 1.1, 1])

    with mid:
        with st.container(border=True):
            st.markdown("#### Sign in")

            email = st.text_input(
                "Email",
                placeholder="you@konverge.ai",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="••••••••",
            )

            submitted = st.button(
                "Log in",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if not email or not password:
                st.error("Enter both email and password.")
            else:
                client = get_client()

                try:
                    token_data = client.login(email, password)
                    st.session_state["token"] = token_data["access_token"]

                    client.token = token_data["access_token"]
                    st.session_state["user"] = client.get_me()

                    st.rerun()

                except APIError as e:
                    st.error(f"Login failed: {e.detail}")

    st.stop()


# ---------------------------------------------------------------------------
# Load live data
# ---------------------------------------------------------------------------
user = st.session_state["user"]
client = get_client()

try:
    invoices = client.list_invoices() or []
except APIError as e:
    invoices = []
    st.warning(f"Couldn't load invoices: {e.detail}")

try:
    matters = {
        m["matter_id"]: m
        for m in (client.list_matters() or [])
    }
except APIError as e:
    matters = {}
    st.warning(f"Couldn't load matters: {e.detail}")

review_q = []

if user["role"] in ("admin", "editor"):
    try:
        review_q = client.review_queue() or []
    except APIError:
        review_q = []

try:
    alerts = client.list_alerts() or []
except APIError as e:
    alerts = []
    st.warning(f"Couldn't load alerts: {e.detail}")

df = pd.DataFrame(invoices)


# ---------------------------------------------------------------------------
# Page heading
# ---------------------------------------------------------------------------
page_header(
    1,
    "Invoice Inbox / Intake Queue",
    f"Welcome back, {user['name'].split()[0]} — every row here is live from the database, "
    "and permissions are enforced by the backend on every request.",
    extra_badge=badge("Live Data", "blue"),
)


# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)

with c1:
    kpi_tile("Total invoices", str(len(df)))

with c2:
    total_spend = (
        pd.to_numeric(df["total_amount"], errors="coerce").fillna(0).sum()
        if not df.empty and "total_amount" in df.columns
        else 0
    )
    kpi_tile("Total spend", f"${total_spend:,.2f}")

with c3:
    kpi_tile("Pending review", str(len(review_q)))

with c4:
    kpi_tile("Active alerts", str(len(alerts)))

st.markdown("&nbsp;")


# ---------------------------------------------------------------------------
# Main dashboard body
#
# Alerts are placed beside the invoice inbox and constrained to a scrollable
# panel. This prevents one or many alerts from pushing the invoice table down.
# ---------------------------------------------------------------------------
main_col, alert_col = st.columns([3.0, 1.25], gap="large")


# ---------------------------------------------------------------------------
# Left: Invoice inbox
# ---------------------------------------------------------------------------
with main_col:
    st.markdown("### Invoice Inbox")

    filter_col_a, filter_col_b, filter_col_c = st.columns(
        [1.35, 1.75, 0.9],
        gap="medium",
    )

    with filter_col_a:
        status_options = ["All"]

        if not df.empty and "status" in df.columns:
            status_options += sorted(
                str(x)
                for x in df["status"].dropna().unique().tolist()
            )

        status_filter = st.selectbox(
            "Status",
            status_options,
            key="home_status_filter",
        )

    with filter_col_b:
        matter_options = ["All"] + sorted(
            {
                str(m.get("name"))
                for m in matters.values()
                if m.get("name")
            }
        )

        matter_filter = st.selectbox(
            "Matter",
            matter_options,
            key="home_matter_filter",
        )

    with filter_col_c:
        st.write("")

        if user["role"] in ("admin", "editor"):
            if st.button(
                "+ New Intake",
                type="primary",
                use_container_width=True,
            ):
                st.switch_page("pages/2_New_Intake.py")

    filtered = list(invoices)

    if status_filter != "All":
        filtered = [
            i for i in filtered
            if i.get("status") == status_filter
        ]

    if matter_filter != "All":
        filtered = [
            i for i in filtered
            if matters.get(i.get("matter_id"), {}).get("name") == matter_filter
        ]

    if not filtered:
        st.info("No invoices match these filters yet.")

    else:
        rows = []

        for i in filtered:
            amount = i.get("total_amount")
            confidence = i.get("confidence_score")

            rows.append(
                {
                    "Invoice": i.get("invoice_no") or f"#{i['invoice_id']}",
                    "Matter": matters.get(
                        i.get("matter_id"),
                        {},
                    ).get(
                        "name",
                        f"Matter {i.get('matter_id', '—')}",
                    ),
                    "Amount": (
                        f"${float(amount):,.2f}"
                        if amount is not None
                        else "—"
                    ),
                    "Confidence": (
                        f"{float(confidence):.0%}"
                        if confidence is not None
                        else "—"
                    ),
                    "Status": str(i.get("status", "—")).replace("_", " "),
                    "_id": i["invoice_id"],
                }
            )

        show_df = pd.DataFrame(rows)

        st.dataframe(
            show_df.drop(columns=["_id"]),
            use_container_width=True,
            hide_index=True,
            height=min(420, max(110, 48 + len(rows) * 35)),
        )

        st.markdown("#### Open an Invoice")

        id_lookup = {
            f"{r['Invoice']} · {r['Matter']}": r["_id"]
            for r in rows
        }

        chosen = st.selectbox(
            "Invoice",
            list(id_lookup.keys()),
            label_visibility="collapsed",
            key="home_invoice_selector",
        )

        open_col, spacer_col = st.columns([1.35, 4.65])

        with open_col:
            if st.button(
                "Open Workspace →",
                use_container_width=True,
            ):
                st.session_state["selected_invoice_id"] = id_lookup[chosen]
                st.switch_page("pages/3_Invoice_Workspace.py")


# ---------------------------------------------------------------------------
# Right: Active alerts
# ---------------------------------------------------------------------------
with alert_col:
    with st.container(border=True):
        st.markdown("### 🔔 Active Alerts")

        if not alerts:
            st.success("No active alerts.")
        else:
            st.caption(
                f"{len(alerts)} active alert"
                f"{'s' if len(alerts) != 1 else ''} · scroll to view all"
            )

            # Native Streamlit fixed-height container.
            # This keeps multiple alerts inside the right-hand panel and
            # provides an independent vertical scrollbar.
            with st.container(height=520, border=False):
                for alert in alerts:
                    render_budget_alert(alert)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
st.markdown("&nbsp;")

chart_left, chart_right = st.columns(
    [1, 1.35],
    gap="large",
)


# ---------------------------------------------------------------------------
# Invoice status breakdown
# ---------------------------------------------------------------------------
with chart_left:
    with st.container(border=True):
        st.markdown("### Invoice status breakdown")

        if df.empty or "status" not in df.columns:
            st.info("No invoices yet.")
        else:
            status_df = (
                df["status"]
                .fillna("unknown")
                .astype(str)
                .value_counts()
                .reset_index()
            )

            status_df.columns = ["status", "count"]

            fig = px.pie(
                status_df,
                names="status",
                values="count",
                hole=0.58,
                color="status",
                color_discrete_map=STATUS_COLORS,
            )

            fig.update_traces(
                textinfo="value+percent",
                textfont_size=13,
                hovertemplate="%{label}: %{value}<extra></extra>",
            )

            fig.update_layout(
                showlegend=True,
                margin=dict(t=10, b=35, l=10, r=10),
                height=315,
                legend=dict(
                    orientation="h",
                    y=-0.08,
                    x=0.5,
                    xanchor="center",
                ),
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
                config={
                    "displayModeBar": True,
                    "displaylogo": False,
                },
            )


# ---------------------------------------------------------------------------
# Spend by matter
# ---------------------------------------------------------------------------
with chart_right:
    with st.container(border=True):
        st.markdown("### Spend by matter")

        if df.empty or "total_amount" not in df.columns:
            st.info("No invoices yet.")
        else:
            chart_df = df.copy()

            chart_df["total_amount"] = pd.to_numeric(
                chart_df["total_amount"],
                errors="coerce",
            ).fillna(0)

            chart_df["matter_name"] = chart_df["matter_id"].map(
                lambda mid: matters.get(
                    mid,
                    {},
                ).get(
                    "name",
                    f"Matter {mid}",
                )
            )

            by_matter = (
                chart_df.groupby(
                    "matter_name",
                    dropna=False,
                )["total_amount"]
                .sum()
                .reset_index()
                .sort_values(
                    "total_amount",
                    ascending=True,
                )
            )

            matter_count = len(by_matter)

            chart_height = min(
                560,
                max(300, 185 + matter_count * 48),
            )

            fig2 = go.Figure(
                go.Bar(
                    x=by_matter["total_amount"],
                    y=by_matter["matter_name"],
                    orientation="h",
                    text=[
                        f"${float(v):,.2f}"
                        for v in by_matter["total_amount"]
                    ],
                    textposition="outside",
                    cliponaxis=False,
                    marker_color="#ff7a00",
                    hovertemplate=(
                        "<b>%{y}</b><br>"
                        "Spend: $%{x:,.2f}"
                        "<extra></extra>"
                    ),
                )
            )

            fig2.update_layout(
                height=chart_height,
                margin=dict(
                    t=15,
                    b=40,
                    l=15,
                    r=95,
                ),
                plot_bgcolor="white",
                paper_bgcolor="white",
                xaxis=dict(
                    title=None,
                    tickprefix="$",
                    separatethousands=True,
                    showgrid=True,
                    zeroline=False,
                ),
                yaxis=dict(
                    title=None,
                    automargin=True,
                ),
                showlegend=False,
            )

            st.plotly_chart(
                fig2,
                use_container_width=True,
                config={
                    "displayModeBar": True,
                    "displaylogo": False,
                },
            )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.caption(
    "Use the sidebar to move through the workbench: "
    "New Intake → Invoice Workspace → Matter & Budget Context → "
    "Validation Check → Review Queue → Review Decision → "
    "Budgets & Alerts → Audit Log → Admin Control."
)
