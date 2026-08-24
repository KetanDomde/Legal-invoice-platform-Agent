import pandas as pd
import plotly.express as px
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
from utils.api_client import (
    get_client,
    APIError,
    DEFAULT_BASE_URL,
)
from utils.alert_cards import render_alert_cards
from utils.notifications import show_flash_messages


st.set_page_config(
    page_title="Konverge | Legal Invoice Platform",
    page_icon="📥",
    layout="wide",
)

inject_base_css()
sidebar_brand()

# Show any queued success/info/warning notifications.
show_flash_messages()


if "base_url" not in st.session_state:
    st.session_state["base_url"] = DEFAULT_BASE_URL


with st.sidebar:

    st.caption("Agent Workbench")

    with st.expander(
        "⚙️ Connection",
        expanded=False,
    ):

        st.session_state["base_url"] = st.text_input(
            "API base URL",
            value=st.session_state["base_url"],
        )

        try:

            get_client().health()
            st.success("API connected")

        except APIError as e:

            st.error(
                f"API unreachable: {e.detail}"
            )


    if st.session_state.get("user"):

        u = st.session_state["user"]

        st.markdown(
            f"""
            <div class="kv-sidebar-card">
                <b>{u['name']}</b><br/>
                {role_badge(u['role'])}
                <div style="font-size:0.8rem;margin-top:4px;">
                    {u['email']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "Log out",
            use_container_width=True,
        ):

            st.session_state.pop(
                "token",
                None,
            )

            st.session_state.pop(
                "user",
                None,
            )

            st.rerun()


render_banner(
    "Legal Invoice Tracking & Spend Management",
    subtitle=(
        "AI-assisted invoice review, budget tracking, "
        "and audit trail — built for outside-counsel spend."
    ),
)


if not st.session_state.get("token"):

    if st.session_state.pop(
        "session_expired",
        False,
    ):

        st.info(
            "Your session has expired. Please log in again."
        )

    left, mid, right = st.columns(
        [1, 1.1, 1]
    )

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

                st.error(
                    "Enter both email and password."
                )

            else:

                try:

                    client = get_client()

                    token_data = client.login(
                        email,
                        password,
                    )

                    st.session_state["token"] = (
                        token_data["access_token"]
                    )

                    client.token = (
                        token_data["access_token"]
                    )

                    st.session_state["user"] = (
                        client.get_me()
                    )

                    st.rerun()

                except APIError as e:

                    st.error(
                        f"Login failed: {e.detail}"
                    )

    st.stop()


user = st.session_state["user"]
client = get_client()


try:

    invoices = (
        client.list_invoices()
        or []
    )

except APIError as e:

    invoices = []

    st.warning(
        f"Couldn't load invoices: {e.detail}"
    )


try:

    matters = {
        m["matter_id"]: m
        for m in client.list_matters()
    }

except APIError as e:

    matters = {}

    st.warning(
        f"Couldn't load matters: {e.detail}"
    )


try:

    alerts = (
        client.list_alerts(
            active_only=True
        )
        or []
    )

except APIError as e:

    alerts = []

    st.warning(
        f"Couldn't load alerts: {e.detail}"
    )


review_q = []

if user["role"] in ("admin", "editor"):

    try:

        review_q = (
            client.review_queue()
        )

    except APIError:

        review_q = []


df = pd.DataFrame(invoices)


page_header(
    1,
    "Invoice Inbox / Intake Queue",
    (
        f"Welcome back, {user['name'].split()[0]} — "
        "live invoice, budget and review data from the database."
    ),
    extra_badge=badge(
        "Live Data",
        "blue",
    ),
)


# ============================================================================
# KPIs + ACTIVE ALERTS
# ============================================================================

main, alert_col = st.columns(
    [4.2, 1.35]
)


with main:

    c1, c2, c3 = st.columns(3)

    with c1:

        kpi_tile(
            "Total invoices",
            str(len(df)),
        )

    with c2:

        kpi_tile(
            "Total spend",
            (
                f"${df['total_amount'].sum():,.2f}"
                if not df.empty
                else "$0.00"
            ),
        )

    with c3:

        kpi_tile(
            "Pending review",
            str(len(review_q)),
        )


with alert_col:

    with st.container(border=True):

        st.markdown(
            "#### 🔔 Active Alerts"
        )

        dismissed = render_alert_cards(
            client,
            alerts[:5],
            key_prefix="home_alert",
            empty_message="No active alerts.",
            compact=True,
        )

        if dismissed:
            st.rerun()

        if len(alerts) > 5:
            st.caption(
                (
                    f"+ {len(alerts) - 5} more active alert(s). "
                    "Open Budgets & Alerts for details."
                )
            )


st.markdown("&nbsp;")


# ============================================================================
# FILTERS
# ============================================================================

col_a, col_b, col_c = st.columns(
    [2, 2, 3]
)


with col_a:

    status_options = (
        ["All"]
        + (
            sorted(
                df["status"]
                .unique()
                .tolist()
            )
            if not df.empty
            else []
        )
    )

    status_filter = st.selectbox(
        "Status",
        status_options,
    )


with col_b:

    matter_options = (
        ["All"]
        + [
            m["name"]
            for m in matters.values()
        ]
    )

    matter_filter = st.selectbox(
        "Matter",
        matter_options,
    )


with col_c:

    st.write("")

    if (
        user["role"]
        in ("admin", "editor")
        and st.button(
            "+ New Intake",
            type="primary",
        )
    ):

        st.switch_page(
            "pages/2_New_Intake.py"
        )


# ============================================================================
# FILTERED INVOICES
# ============================================================================

filtered = invoices


if status_filter != "All":

    filtered = [
        i
        for i in filtered
        if i["status"] == status_filter
    ]


if matter_filter != "All":

    filtered = [
        i
        for i in filtered
        if (
            matters
            .get(
                i["matter_id"],
                {},
            )
            .get("name")
            == matter_filter
        )
    ]


if not filtered:

    st.info(
        "No invoices match these filters yet."
    )

else:

    rows = []

    for i in filtered:

        rows.append(
            {
                "Invoice": (
                    i.get("invoice_no")
                    or f"#{i['invoice_id']}"
                ),

                "Matter": (
                    matters
                    .get(
                        i["matter_id"],
                        {},
                    )
                    .get(
                        "name",
                        f"Matter {i['matter_id']}",
                    )
                ),

                "Amount": (
                    f"${i['total_amount']:,.2f}"
                    if i.get("total_amount")
                    is not None
                    else "—"
                ),

                "Confidence": (
                    f"{i['confidence_score']:.0%}"
                    if i.get("confidence_score")
                    is not None
                    else "—"
                ),

                "Status": i["status"],

                "_id": i["invoice_id"],
            }
        )


    show_df = pd.DataFrame(rows)

    st.dataframe(
        show_df.drop(
            columns=["_id"]
        ),
        use_container_width=True,
        hide_index=True,
    )


    st.markdown(
        "#### Open an Invoice"
    )


    id_lookup = {
        (
            f"{r['Invoice']} · "
            f"{r['Matter']}"
        ): r["_id"]
        for r in rows
    }


    chosen = st.selectbox(
        "Invoice",
        list(id_lookup.keys()),
        label_visibility="collapsed",
    )


    if st.button(
        "Open Workspace →"
    ):

        st.session_state[
            "selected_invoice_id"
        ] = id_lookup[chosen]

        st.switch_page(
            "pages/3_Invoice_Workspace.py"
        )


st.markdown("&nbsp;")


# ============================================================================
# CHARTS
# ============================================================================

left, right = st.columns(
    [1, 1.3]
)


with left:

    with st.container(border=True):

        st.markdown(
            "##### Invoice status breakdown"
        )

        if not df.empty:

            counts = (
                df["status"]
                .value_counts()
                .reset_index()
            )

            counts.columns = [
                "status",
                "count",
            ]

            fig = px.pie(
                counts,
                names="status",
                values="count",
                hole=0.55,
                color="status",
                color_discrete_map=STATUS_COLORS,
            )

            fig.update_traces(
                textinfo="value+percent",
                textfont_size=13,
            )

            fig.update_layout(
                showlegend=True,
                margin=dict(
                    t=10,
                    b=10,
                    l=10,
                    r=10,
                ),
                height=300,
                legend=dict(
                    orientation="h",
                    y=-0.15,
                ),
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

        else:

            st.info(
                "No invoices yet."
            )


with right:

    with st.container(border=True):

        st.markdown(
            "##### Spend by matter"
        )

        if not df.empty:

            import plotly.graph_objects as go

            from utils.theme import ORANGE


            chart_df = df.copy()


            chart_df[
                "matter_name"
            ] = chart_df[
                "matter_id"
            ].map(
                lambda mid: (
                    matters
                    .get(
                        mid,
                        {},
                    )
                    .get(
                        "name",
                        f"Matter {mid}",
                    )
                )
            )


            by_matter = (
                chart_df
                .groupby("matter_name")[
                    "total_amount"
                ]
                .sum()
                .reset_index()
                .sort_values(
                    "total_amount"
                )
            )


            fig2 = go.Figure(
                go.Bar(
                    x=by_matter[
                        "total_amount"
                    ],
                    y=by_matter[
                        "matter_name"
                    ],
                    orientation="h",
                    marker_color=ORANGE,
                    text=[
                        f"${value:,.2f}"
                        for value in by_matter[
                            "total_amount"
                        ]
                    ],
                    textposition="outside",
                )
            )


            fig2.update_layout(
                margin=dict(
                    t=10,
                    b=10,
                    l=10,
                    r=30,
                ),
                height=300,
                xaxis_title=None,
                yaxis_title=None,
                plot_bgcolor="white",
            )


            st.plotly_chart(
                fig2,
                use_container_width=True,
            )

        else:

            st.info(
                "No invoices yet."
            )


st.caption(
    (
        "Use the sidebar to move through the workbench: "
        "New Intake → Invoice Workspace → Matter & Budget Context → "
        "Validation Check → Review Queue → Review Decision → "
        "Budgets & Alerts → Audit Log → Admin Control."
    )
)