import pandas as pd
import streamlit as st

from utils.theme import (
    badge,
    inject_base_css,
    notice,
    page_header,
    sidebar_brand,
)
from utils.api_client import (
    APIError,
    get_client,
    require_login,
)
from utils.alert_cards import render_alert_cards
from utils.notifications import (
    flash,
    show_flash_messages,
)


st.set_page_config(
    page_title="Budgets & Alerts | Konverge",
    page_icon="💰",
    layout="wide",
)

inject_base_css()
sidebar_brand()
require_login()

# Show queued floating notifications immediately after the rerun.
show_flash_messages()

client = get_client()
user = st.session_state["user"]


try:
    hierarchy = client.get_budget_hierarchy() or []
    active_alerts = client.list_alerts(
        active_only=True
    ) or []

except APIError as exc:
    st.error(
        f"Couldn't load budget data: {exc.detail}"
    )
    st.stop()


page_header(
    8,
    "Budgets & Alerts",
    (
        "Current budget position, related invoices, adjustment history, "
        "and unresolved alerts in one place."
    ),
    extra_badge=badge(
        f"{len(active_alerts)} active alert(s)",
        "orange" if active_alerts else "green",
    ),
)


left, right = st.columns([3.2, 1])


# ============================================================================
# ACTIVE ALERT CARDS
# ============================================================================

with right:
    with st.container(border=True):
        st.markdown("#### 🔔 Active Alerts")

        dismissed = render_alert_cards(
            client,
            active_alerts,
            key_prefix="budgets_alert",
            empty_message="No active budget alerts.",
            compact=True,
        )

        if dismissed:
            st.rerun()


# ============================================================================
# BUDGET HIERARCHY
# ============================================================================

with left:
    if not hierarchy:
        st.info(
            "No matters with budgets are available yet. "
            "Budgets are created automatically from invoice intake."
        )

    for firm in hierarchy:

        # --------------------------------------------------------------------
        # Open only firms requiring admin attention.
        #
        # A firm opens when it has:
        # - the newest invoice,
        # - an over-budget matter,
        # - a matter at/above its threshold,
        # - an active alert.
        #
        # All other firms stay collapsed.
        # --------------------------------------------------------------------
        expanded = bool(
            firm.get("requires_attention", False)
        )

        with st.expander(
            (
                f"🏢 {firm['firm_name']}  ·  "
                f"{len(firm['matters'])} matter(s)"
            ),
            expanded=expanded,
        ):
            if firm.get("firm_address"):
                st.caption(
                    firm["firm_address"]
                )

            for matter in firm["matters"]:

                title = (
                    f"{matter.get('matter_no') or 'Matter'} "
                    f"— {matter['matter_name']}"
                )

                st.markdown(
                    f"### {title}"
                )

                # ------------------------------------------------------------
                # Budget metrics
                # ------------------------------------------------------------

                m1, m2, m3, m4 = st.columns(4)

                m1.metric(
                    "Effective budget",
                    f"${matter['allocated']:,.2f}",
                )

                m2.metric(
                    "Approved spend",
                    f"${matter['utilized']:,.2f}",
                )

                m3.metric(
                    "Remaining",
                    f"${matter['remaining']:,.2f}",
                )

                m4.metric(
                    "Utilization",
                    f"{matter['pct_used']:.1f}%",
                )

                st.progress(
                    min(
                        matter["pct_used"] / 100,
                        1.0,
                    ),
                    text=(
                        f"Current utilization: "
                        f"{matter['pct_used']:.1f}% · "
                        f"Alert threshold: "
                        f"{matter['threshold_pct']:.0f}%"
                    ),
                )

                # ------------------------------------------------------------
                # Budget state
                # ------------------------------------------------------------

                if matter["over_budget"]:
                    notice(
                        "OVER BUDGET — the approved spend is above "
                        "the effective budget."
                    )

                elif matter["threshold_reached"]:
                    notice(
                        "Budget threshold reached. This is a warning; "
                        "it does not by itself block approval."
                    )

                else:
                    notice(
                        "Within the configured budget threshold.",
                        success=True,
                    )

                # ------------------------------------------------------------
                # Related invoices
                # ------------------------------------------------------------

                rows = []

                for inv in matter["invoices"]:

                    invoice_label = (
                        inv.get("invoice_no")
                        or f"#{inv['invoice_id']}"
                    )

                    if inv.get("is_newest_invoice"):
                        invoice_label += " 🆕"

                    rows.append(
                        {
                            "Invoice No.": invoice_label,

                            "Invoice Amount": (
                                f"${inv['amount']:,.2f}"
                            ),

                            "Invoice Status": (
                                inv["status"]
                                .replace("_", " ")
                                .title()
                            ),

                            "Budget Result": (
                                inv["budget_result"]
                                .replace("_", " ")
                                .title()
                            ),

                            "Remaining After Invoice": (
                                f"${inv['remaining_after_invoice']:,.2f}"
                            ),

                            "Projected Utilization": (
                                f"{inv.get('projected_utilization', 0):.1f}%"
                                if inv.get(
                                    "projected_utilization"
                                ) is not None
                                else "—"
                            ),

                            "Needs Attention": (
                                "Yes"
                                if inv["needs_attention"]
                                else "No"
                            ),

                            "Review Reason": (
                                inv.get("validation_message")
                                or "—"
                            ),

                            "_attention": (
                                inv["needs_attention"]
                            ),
                        }
                    )

                st.markdown(
                    "#### Related Invoices"
                )

                if rows:
                    df = pd.DataFrame(rows)

                    display = df.drop(
                        columns=["_attention"]
                    )

                    def highlight_attention(row):
                        return [
                            (
                                "background-color: #ffe4e6; "
                                "font-weight: 600"
                            )
                            if rows[row.name][
                                "_attention"
                            ]
                            else ""
                            for _ in row
                        ]

                    st.dataframe(
                        display.style.apply(
                            highlight_attention,
                            axis=1,
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                    st.caption(
                        "Rows highlighted in red require budget attention."
                    )

                else:
                    st.caption(
                        "No invoices are associated with this matter yet."
                    )

                # ------------------------------------------------------------
                # Adjust budget
                # ------------------------------------------------------------

                if user["role"] == "admin":

                    st.markdown(
                        "#### Adjust Budget"
                    )

                    attention_invoices = [
                        inv
                        for inv in matter["invoices"]
                        if (
                            inv["status"] == "pending_review"
                            and inv["needs_attention"]
                        )
                    ]

                    options = {
                        "No specific invoice": None
                    }

                    for inv in attention_invoices:

                        invoice_label = (
                            inv.get("invoice_no")
                            or f"#{inv['invoice_id']}"
                        )

                        options[
                            invoice_label
                        ] = inv["invoice_id"]

                    with st.form(
                        f"adjust_{matter['budget_id']}"
                    ):

                        related_label = st.selectbox(
                            "Related invoice",
                            list(options.keys()),
                            key=(
                                f"rel_{matter['budget_id']}"
                            ),
                        )

                        amount = st.number_input(
                            (
                                "Adjustment amount "
                                "(+ increase / - decrease)"
                            ),
                            value=0.0,
                            step=1000.0,
                            key=(
                                f"amount_{matter['budget_id']}"
                            ),
                        )

                        reason = st.text_area(
                            "Reason for adjustment (required)",
                            placeholder=(
                                "Example: Additional litigation work "
                                "approved."
                            ),
                            key=(
                                f"reason_{matter['budget_id']}"
                            ),
                        )

                        confirmed = st.checkbox(
                            (
                                "I confirm this adjustment will be "
                                "recorded in the audit log."
                            ),
                            key=(
                                f"confirm_{matter['budget_id']}"
                            ),
                        )

                        submitted = st.form_submit_button(
                            "Adjust budget",
                            type="primary",
                        )

                    if submitted:

                        if amount == 0:
                            st.error(
                                "Adjustment amount cannot be zero."
                            )

                        elif not reason.strip():
                            st.error(
                                "A reason is required."
                            )

                        elif not confirmed:
                            st.error(
                                "Please confirm the adjustment."
                            )

                        else:

                            try:
                                result = client.adjust_budget(
                                    matter["budget_id"],
                                    amount,
                                    reason,
                                    confirmed,
                                    options[related_label],
                                )

                                reconciliation = result.get(
                                    "reconciliation",
                                    {},
                                )

                                approved = reconciliation.get(
                                    "auto_approved",
                                    [],
                                )

                                pending = reconciliation.get(
                                    "still_pending",
                                    [],
                                )

                                flash(
                                    result.get(
                                        "message",
                                        "Budget updated.",
                                    ),
                                    "success",
                                )

                                if approved:
                                    flash(
                                        (
                                            "Auto-approved after budget "
                                            "reconciliation: "
                                            + ", ".join(
                                                x.get("invoice_no")
                                                or (
                                                    f"#{x['invoice_id']}"
                                                )
                                                for x in approved
                                            )
                                        ),
                                        "success",
                                    )

                                if pending:
                                    flash(
                                        (
                                            f"{len(pending)} invoice(s) "
                                            "still require review."
                                        ),
                                        "warning",
                                    )

                                st.rerun()

                            except APIError as exc:
                                flash(
                                    exc.detail,
                                    "warning",
                                )
                                st.rerun()

                st.divider()