import html
import re

import pandas as pd
import streamlit as st

from utils.theme import badge, inject_base_css, notice, page_header, sidebar_brand
from utils.api_client import APIError, get_client, require_login, require_role

st.set_page_config(page_title="Budgets & Alerts | Konverge", page_icon="💰", layout="wide")
inject_base_css()
sidebar_brand()
require_login()


# ---------------------------------------------------------------------------
# Active alert styling
# Keep this UI consistent with the Home page. The panel scrolls independently
# so multiple alerts do not affect the budget section layout.
# ---------------------------------------------------------------------------
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
        font-style: normal;
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
        font-style: normal;
    }
    .budget-alert-message {
        font-size: 0.86rem;
        line-height: 1.55;
        color: #1f2937;
        margin-top: 8px;
        font-style: normal !important;
    }
    .budget-alert-footer {
        font-size: 0.76rem;
        color: #64748b;
        margin-top: 8px;
        font-style: normal !important;
    }
    .budget-alert-card em,
    .budget-alert-card i {
        font-style: normal !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _clean_alert_text(value) -> str:
    """Strip formatting from alert text so all alert fonts stay consistent."""
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[*_`]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _alert_kind(alert: dict) -> str:
    value = " ".join(
        str(alert.get(k) or "")
        for k in ("type", "alert_type", "message")
    ).lower()
    if any(
        x in value
        for x in ("over_budget", "over budget", "overrun", "exceed")
    ):
        return "over-budget"
    return "threshold"


def render_budget_alert(alert: dict) -> None:
    """Render one alert using the same card structure as Home."""
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
    message = (
        _clean_alert_text(alert.get("message"))
        or "Budget attention required."
    )
    matter = f"{matter_no} — {matter_name}" if matter_no else matter_name

    utilization = alert.get("utilization_pct")
    threshold = alert.get("threshold_pct")
    utilization_text = (
        f"{float(utilization):.1f}%" if utilization is not None else "—"
    )
    threshold_text = (
        f"{float(threshold):.1f}%" if threshold is not None else "—"
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

def _clear_adjust_budget_form(budget_id: int) -> None:
    """Clear all widgets belonging to a completed budget adjustment form."""
    for key in (
        f"rel_{budget_id}",
        f"amount_{budget_id}",
        f"reason_{budget_id}",
        f"confirm_{budget_id}",
    ):
        st.session_state.pop(key, None)


def _show_adjustment_result() -> None:
    """Show one adjustment result after the page reruns, then consume it."""
    result = st.session_state.pop("budget_adjustment_result", None)
    if not result:
        return

    message = result.get("message")
    level = result.get("level", "success")

    if level == "warning":
        st.warning(message)
    elif level == "error":
        st.error(message)
    else:
        st.success(message)


client = get_client()
user = st.session_state["user"]

try:
    hierarchy = client.get_budget_hierarchy() or []
    active_alerts = client.list_alerts(active_only=True) or []
except APIError as exc:
    st.error(f"Couldn't load budget data: {exc.detail}")
    st.stop()

_show_adjustment_result()

page_header(
    8,
    "Budgets & Alerts",
    "One source of truth for budget position, invoice impact, adjustments, and unresolved alerts.",
    extra_badge=badge(f"{len(active_alerts)} active alert(s)", "orange" if active_alerts else "green"),
)

left, right = st.columns([3.2, 1])

with right:
    with st.container(border=True):
        st.markdown("### 🔔 Active Alerts")

        if not active_alerts:
            st.success("No active alerts.")
        else:
            st.caption(
                f"{len(active_alerts)} active alert"
                f"{'s' if len(active_alerts) != 1 else ''} · scroll to view all"
            )

            # IMPORTANT: use Streamlit's native height-constrained container here.
            # A raw HTML div cannot reliably contain Streamlit elements because
            # each st.markdown() is rendered as a separate Streamlit block.
            # The native container makes the alert cards themselves scrollable.
            with st.container(height=520, border=False):
                for alert in active_alerts:
                    render_budget_alert(alert)

with left:
    if not hierarchy:
        st.info("No matters with budgets are available yet. Budgets are created automatically from invoice intake.")

    for firm in hierarchy:
        # Open only firms containing an invoice that currently needs admin
        # attention. This restores the original useful landing state without
        # changing any budget/invoice data or reconciliation logic.
        firm_needs_attention = any(
            inv.get("needs_attention", False)
            for matter in firm.get("matters", [])
            for inv in matter.get("invoices", [])
        )

        with st.expander(
            f"🏢 {firm['firm_name']}  ·  {len(firm['matters'])} matter(s)",
            expanded=firm_needs_attention,
        ):
            if firm.get("firm_address"):
                st.caption(firm["firm_address"])

            for matter in firm["matters"]:
                title = f"{matter.get('matter_no') or 'Matter'} — {matter['matter_name']}"
                st.markdown(f"### {title}")

                # ------------------------------------------------------------------
                # BUDGET POSITION
                #
                # Keep the original four metric names. For a pending-review
                # invoice, Remaining and Current utilization use the projected
                # position, while Approved spend remains ledger-backed.
                # ------------------------------------------------------------------
                allocated = float(matter.get("allocated") or 0)
                approved_spend = float(matter.get("utilized") or 0)
                approved_remaining = float(matter.get("remaining") or 0)
                approved_pct = float(matter.get("pct_used") or 0)
                pending_amount = float(matter.get("pending_invoice_amount") or 0)

                if pending_amount > 0:
                    display_remaining = float(
                        matter.get("projected_remaining", approved_remaining)
                    )
                    display_pct = float(
                        matter.get("projected_pct_used", approved_pct)
                    )
                    pending_count = int(matter.get("pending_invoice_count") or 0)
                else:
                    display_remaining = approved_remaining
                    display_pct = approved_pct
                    pending_count = 0

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Effective budget", f"${allocated:,.2f}")
                m2.metric("Approved spend", f"${approved_spend:,.2f}")
                m3.metric("Remaining", f"${display_remaining:,.2f}")
                m4.metric("Current utilization", f"{display_pct:.1f}%")

                if pending_amount > 0:
                    pending_label = (
                        "pending review invoice"
                        if pending_count == 1
                        else "pending review invoices"
                    )
                    st.progress(
                        min(display_pct / 100, 1.0),
                        text=(
                            f"Projected utilization: {display_pct:.1f}% · "
                            f"Includes {pending_count} {pending_label} "
                            f"(${pending_amount:,.2f}) · "
                            f"Alert threshold: {matter['threshold_pct']:.0f}%"
                        ),
                    )

                    if matter.get("projected_over_budget", False):
                        notice(
                            "OVER BUDGET — pending review invoice(s) would exceed "
                            "the effective budget."
                        )
                    elif matter.get("projected_threshold_reached", False):
                        notice(
                            "Budget threshold reached. Pending review invoice(s) "
                            f"take projected utilization to {display_pct:.1f}%. "
                            "This is a warning; it does not by itself block approval."
                        )
                    else:
                        notice(
                            "Within the configured budget threshold after including "
                            "pending review invoice(s).",
                            success=True,
                        )
                else:
                    st.progress(
                        min(display_pct / 100, 1.0),
                        text=(
                            f"Current utilization: {display_pct:.1f}% · "
                            f"Alert threshold: {matter['threshold_pct']:.0f}%"
                        ),
                    )

                    if matter["over_budget"]:
                        notice(
                            "OVER BUDGET — the approved spend is above the effective budget."
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

                rows = []
                for inv in matter["invoices"]:
                    rows.append(
                        {
                            "Invoice No.": inv.get("invoice_no") or f"#{inv['invoice_id']}",
                            "Invoice Amount": f"${inv['amount']:,.2f}",
                            "Invoice Status": inv["status"].replace("_", " ").title(),
                            "Budget Result": inv["budget_result"].replace("_", " ").title(),
                            "Projected Utilization": f"{float(inv.get('projected_utilization') or 0):.1f}%",
                            "Remaining After Invoice": f"${inv['remaining_after_invoice']:,.2f}",
                            "Needs Attention": "Yes" if inv["needs_attention"] else "No",
                            "Review Reason": inv.get("validation_message") or "—",
                            "_attention": inv["needs_attention"],
                        }
                    )

                st.markdown("#### Related Invoices")
                if rows:
                    df = pd.DataFrame(rows)
                    display = df.drop(columns=["_attention"])

                    def highlight_attention(row):
                        return [
                            "background-color: #ffe4e6; font-weight: 600" if rows[row.name]["_attention"] else ""
                            for _ in row
                        ]

                    st.dataframe(
                        display.style.apply(highlight_attention, axis=1),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption("Rows highlighted in red require budget attention. This remains reliable even with many invoices.")
                else:
                    st.caption("No invoices are associated with this matter yet.")

                if user["role"] == "admin":
                    st.markdown("#### Adjust Budget")
                    attention_invoices = [
                        inv for inv in matter["invoices"]
                        if inv["status"] == "pending_review" and inv["needs_attention"]
                    ]
                    options = {"No specific invoice": None}
                    for inv in attention_invoices:
                        options[inv.get("invoice_no") or f"#{inv['invoice_id']}"] = inv["invoice_id"]

                    with st.form(f"adjust_{matter['budget_id']}"):
                        related_label = st.selectbox("Related invoice", list(options.keys()), key=f"rel_{matter['budget_id']}")
                        amount = st.number_input(
                            "Adjustment amount (+ increase / - decrease)",
                            value=0.0,
                            step=1000.0,
                            key=f"amount_{matter['budget_id']}",
                        )
                        reason = st.text_area(
                            "Reason for adjustment (required)",
                            placeholder="Example: Additional litigation work approved.",
                            key=f"reason_{matter['budget_id']}",
                        )
                        confirmed = st.checkbox(
                            "I confirm this adjustment will be recorded in the audit log.",
                            key=f"confirm_{matter['budget_id']}",
                        )
                        submitted = st.form_submit_button("Adjust budget", type="primary")

                    if submitted:
                        if amount == 0:
                            st.error("Adjustment amount cannot be zero.")
                        elif not reason.strip():
                            st.error("A reason is required.")
                        elif not confirmed:
                            st.error("Please confirm the adjustment.")
                        else:
                            try:
                                result = client.adjust_budget(
                                    matter["budget_id"],
                                    amount,
                                    reason.strip(),
                                    confirmed,
                                    options[related_label],
                                )

                                rec = result.get("reconciliation", {})
                                approved = rec.get("auto_approved", []) or []
                                pending = rec.get("still_pending", []) or []

                                action = (
                                    "increased"
                                    if float(amount) > 0
                                    else "decreased"
                                )

                                # Show exactly ONE result message after rerun.
                                # If the budget change removed the budget blocker,
                                # explicitly tell the admin that the invoice was
                                # approved. Otherwise explain that it remains pending.
                                if approved:
                                    invoice_names = ", ".join(
                                        x.get("invoice_no")
                                        or f"#{x['invoice_id']}"
                                        for x in approved
                                    )
                                    if len(approved) == 1:
                                        message = (
                                            f"Budget {action} successfully. "
                                            f"Invoice {invoice_names} was approved successfully "
                                            "after budget reconciliation."
                                        )
                                    else:
                                        message = (
                                            f"Budget {action} successfully. "
                                            f"{len(approved)} invoice(s) were approved successfully "
                                            "after budget reconciliation."
                                        )
                                    level = "success"
                                elif pending:
                                    message = (
                                        f"Budget {action} successfully. "
                                        f"{len(pending)} invoice(s) remain pending review "
                                        "because other review issues still exist."
                                    )
                                    level = "warning"
                                else:
                                    message = result.get(
                                        "message",
                                        f"Budget {action} successfully.",
                                    )
                                    level = "success"

                                st.session_state["budget_adjustment_result"] = {
                                    "message": message,
                                    "level": level,
                                }

                                # Reset the widgets before rerunning. Without this,
                                # Streamlit keeps the old amount/reason/checkbox values
                                # and the admin can accidentally submit the same
                                # adjustment again.
                                _clear_adjust_budget_form(matter["budget_id"])
                                st.rerun()

                            except APIError as exc:
                                st.error(exc.detail)

                st.divider()

# import html
# import re

# import pandas as pd
# import streamlit as st

# from utils.theme import badge, inject_base_css, notice, page_header, sidebar_brand
# from utils.api_client import APIError, get_client, require_login, require_role
# from utils.notifications import flash

# st.set_page_config(page_title="Budgets & Alerts | Konverge", page_icon="💰", layout="wide")
# inject_base_css()
# sidebar_brand()
# require_login()


# # ---------------------------------------------------------------------------
# # Active alert styling
# # Keep this UI consistent with the Home page. The panel scrolls independently
# # so multiple alerts do not affect the budget section layout.
# # ---------------------------------------------------------------------------
# st.markdown(
#     """
#     <style>
#     .budget-alert-panel {
#         max-height: 520px;
#         overflow-y: auto;
#         padding: 2px 4px 4px 2px;
#     }
#     .budget-alert-card {
#         border: 1px solid #d9d9e2;
#         border-radius: 10px;
#         padding: 12px 13px;
#         margin: 0 0 10px 0;
#         background: #ffffff;
#         font-family: inherit;
#         line-height: 1.5;
#         overflow-wrap: anywhere;
#     }
#     .budget-alert-card.over-budget {
#         border-left: 5px solid #dc2626;
#         background: #fff7f7;
#     }
#     .budget-alert-card.threshold {
#         border-left: 5px solid #f59e0b;
#         background: #fffbeb;
#     }
#     .budget-alert-title {
#         font-size: 0.95rem;
#         font-weight: 700;
#         line-height: 1.35;
#         margin-bottom: 8px;
#         font-style: normal;
#     }
#     .budget-alert-card.over-budget .budget-alert-title {
#         color: #b91c1c;
#     }
#     .budget-alert-card.threshold .budget-alert-title {
#         color: #92400e;
#     }
#     .budget-alert-meta {
#         font-size: 0.82rem;
#         line-height: 1.5;
#         color: #64748b;
#         margin: 3px 0;
#         font-style: normal;
#     }
#     .budget-alert-message {
#         font-size: 0.86rem;
#         line-height: 1.55;
#         color: #1f2937;
#         margin-top: 8px;
#         font-style: normal !important;
#     }
#     .budget-alert-footer {
#         font-size: 0.76rem;
#         color: #64748b;
#         margin-top: 8px;
#         font-style: normal !important;
#     }
#     .budget-alert-card em,
#     .budget-alert-card i {
#         font-style: normal !important;
#     }
#     </style>
#     """,
#     unsafe_allow_html=True,
# )


# def _clean_alert_text(value) -> str:
#     """Strip formatting from alert text so all alert fonts stay consistent."""
#     if value is None:
#         return ""
#     text = html.unescape(str(value))
#     text = re.sub(r"<[^>]+>", "", text)
#     text = re.sub(r"[*_`]+", "", text)
#     text = re.sub(r"\s+", " ", text)
#     return text.strip()


# def _alert_kind(alert: dict) -> str:
#     value = " ".join(
#         str(alert.get(k) or "")
#         for k in ("type", "alert_type", "message")
#     ).lower()
#     if any(
#         x in value
#         for x in ("over_budget", "over budget", "overrun", "exceed")
#     ):
#         return "over-budget"
#     return "threshold"


# def render_budget_alert(alert: dict) -> None:
#     """Render one alert using the same card structure as Home."""
#     kind = _alert_kind(alert)
#     title = (
#         "⚠️ Over Budget Detected"
#         if kind == "over-budget"
#         else "⚠️ Budget Threshold Reached"
#     )

#     firm = _clean_alert_text(alert.get("firm_name")) or "—"
#     matter_no = _clean_alert_text(alert.get("matter_no"))
#     matter_name = _clean_alert_text(alert.get("matter_name")) or "—"
#     invoice_no = _clean_alert_text(alert.get("invoice_no"))
#     message = (
#         _clean_alert_text(alert.get("message"))
#         or "Budget attention required."
#     )
#     matter = f"{matter_no} — {matter_name}" if matter_no else matter_name

#     utilization = alert.get("utilization_pct")
#     threshold = alert.get("threshold_pct")
#     utilization_text = (
#         f"{float(utilization):.1f}%" if utilization is not None else "—"
#     )
#     threshold_text = (
#         f"{float(threshold):.1f}%" if threshold is not None else "—"
#     )

#     st.markdown(
#         f"""
#         <div class="budget-alert-card {kind}">
#             <div class="budget-alert-title">{title}</div>
#             <div class="budget-alert-meta">🏢 <b>Firm:</b> {html.escape(firm)}</div>
#             <div class="budget-alert-meta">📁 <b>Matter:</b> {html.escape(matter)}</div>
#             <div class="budget-alert-meta">📄 <b>Invoice:</b> {html.escape(invoice_no or "—")}</div>
#             <div class="budget-alert-message">{html.escape(message)}</div>
#             <div class="budget-alert-footer">
#                 Utilization: <b>{utilization_text}</b>
#                 &nbsp;·&nbsp;
#                 Threshold: <b>{threshold_text}</b>
#             </div>
#         </div>
#         """,
#         unsafe_allow_html=True,
#     )

# client = get_client()
# user = st.session_state["user"]

# try:
#     hierarchy = client.get_budget_hierarchy() or []
#     active_alerts = client.list_alerts(active_only=True) or []
# except APIError as exc:
#     st.error(f"Couldn't load budget data: {exc.detail}")
#     st.stop()

# page_header(
#     8,
#     "Budgets & Alerts",
#     "One source of truth for budget position, invoice impact, adjustments, and unresolved alerts.",
#     extra_badge=badge(f"{len(active_alerts)} active alert(s)", "orange" if active_alerts else "green"),
# )

# left, right = st.columns([3.2, 1])

# with right:
#     with st.container(border=True):
#         st.markdown("### 🔔 Active Alerts")

#         if not active_alerts:
#             st.success("No active alerts.")
#         else:
#             st.caption(
#                 f"{len(active_alerts)} active alert"
#                 f"{'s' if len(active_alerts) != 1 else ''} · scroll to view all"
#             )

#             # IMPORTANT: use Streamlit's native height-constrained container here.
#             # A raw HTML div cannot reliably contain Streamlit elements because
#             # each st.markdown() is rendered as a separate Streamlit block.
#             # The native container makes the alert cards themselves scrollable.
#             with st.container(height=520, border=False):
#                 for alert in active_alerts:
#                     render_budget_alert(alert)

# with left:
#     if not hierarchy:
#         st.info("No matters with budgets are available yet. Budgets are created automatically from invoice intake.")

#     for firm in hierarchy:
#         # Open only firms containing an invoice that currently needs admin
#         # attention. This restores the original useful landing state without
#         # changing any budget/invoice data or reconciliation logic.
#         firm_needs_attention = any(
#             inv.get("needs_attention", False)
#             for matter in firm.get("matters", [])
#             for inv in matter.get("invoices", [])
#         )

#         with st.expander(
#             f"🏢 {firm['firm_name']}  ·  {len(firm['matters'])} matter(s)",
#             expanded=firm_needs_attention,
#         ):
#             if firm.get("firm_address"):
#                 st.caption(firm["firm_address"])

#             for matter in firm["matters"]:
#                 title = f"{matter.get('matter_no') or 'Matter'} — {matter['matter_name']}"
#                 st.markdown(f"### {title}")

#                 # m1, m2, m3, m4 = st.columns(4)
#                 # m1.metric("Effective budget", f"${matter['allocated']:,.2f}")
#                 # m2.metric("Approved spend", f"${matter['utilized']:,.2f}")
#                 # m3.metric("Remaining", f"${matter['remaining']:,.2f}")
#                 # m4.metric("Utilization", f"{matter['pct_used']:.1f}%")

#                 # st.progress(
#                 #     min(matter["pct_used"] / 100, 1.0),
#                 #     text=(
#                 #         f"Current utilization: {matter['pct_used']:.1f}% · "
#                 #         f"Alert threshold: {matter['threshold_pct']:.0f}%"
#                 #     ),
#                 # )

#                 # if matter["over_budget"]:
#                 #     notice("OVER BUDGET — the approved spend is above the effective budget.")
#                 # elif matter["threshold_reached"]:
#                 #     notice("Budget threshold reached. This is a warning; it does not by itself block approval.")
#                 # else:
#                 #     notice("Within the configured budget threshold.", success=True)
#                 # ------------------------------------------------------------------
#                 # CURRENT APPROVED BUDGET POSITION
#                 # ------------------------------------------------------------------
#                 m1, m2, m3, m4 = st.columns(4)

#                 m1.metric(
#                     "Effective budget",
#                     f"${matter['allocated']:,.2f}",
#                 )

#                 m2.metric(
#                     "Approved spend",
#                     f"${matter['utilized']:,.2f}",
#                 )

#                 m3.metric(
#                     "Remaining",
#                     f"${matter['remaining']:,.2f}",
#                 )

#                 m4.metric(
#                     "Current utilization",
#                     f"{matter['pct_used']:.1f}%",
#                 )

#                 st.progress(
#                     min(matter["pct_used"] / 100, 1.0),
#                     text=(
#                         f"Current approved utilization: "
#                         f"{matter['pct_used']:.1f}% · "
#                         f"Alert threshold: "
#                         f"{matter['threshold_pct']:.0f}%"
#                     ),
#                 )

#                 # ------------------------------------------------------------------
#                 # PROJECTED POSITION
#                 # Include the pending-review invoice without posting it to the
#                 # approved BudgetLedger.
#                 # ------------------------------------------------------------------
#                 pending_amount = float(
#                     matter.get("pending_invoice_amount") or 0
#                 )

#                 if pending_amount > 0:
#                     st.markdown("#### Pending Invoice Impact")

#                     p1, p2, p3, p4 = st.columns(4)

#                     p1.metric(
#                         "Pending invoice",
#                         f"${pending_amount:,.2f}",
#                     )

#                     p2.metric(
#                         "Projected spend",
#                         f"${matter.get('projected_utilized', matter['utilized']):,.2f}",
#                     )

#                     p3.metric(
#                         "Projected remaining",
#                         f"${matter.get('projected_remaining', matter['remaining']):,.2f}",
#                     )

#                     p4.metric(
#                         "Projected utilization",
#                         f"{matter.get('projected_pct_used', matter['pct_used']):.1f}%",
#                     )

#                     projected_pct = float(
#                         matter.get("projected_pct_used", matter["pct_used"]) or 0
#                     )

#                     st.progress(
#                         min(projected_pct / 100, 1.0),
#                         text=(
#                             f"Projected utilization: "
#                             f"{projected_pct:.1f}% · "
#                             f"Includes pending invoice"
#                         ),
#                     )

#                     if matter.get("projected_over_budget", False):
#                         notice(
#                             "OVER BUDGET — the pending invoice would exceed "
#                             "the effective budget.",
#                         )
#                     elif matter.get("projected_threshold_reached", False):
#                         notice(
#                             "Budget threshold reached — the pending invoice "
#                             "would take utilization to the displayed projected level. "
#                             "This is a warning and does not by itself block approval.",
#                         )
#                     else:
#                         notice(
#                             "Pending invoice remains within the configured budget threshold.",
#                             success=True,
#                         )

#                 else:
#                     # No pending invoice, so current approved state is the effective state.
#                     if matter["over_budget"]:
#                         notice(
#                             "OVER BUDGET — the approved spend is above the effective budget."
#                         )
#                     elif matter["threshold_reached"]:
#                         notice(
#                             "Budget threshold reached. This is a warning; "
#                             "it does not by itself block approval."
#                         )
#                     else:
#                         notice(
#                             "Within the configured budget threshold.",
#                             success=True,
#                         )

#                 # rows = []
#                 # for inv in matter["invoices"]:
#                 #     rows.append(
#                 #         {
#                 #             "Invoice No.": inv.get("invoice_no") or f"#{inv['invoice_id']}",
#                 #             "Invoice Amount": f"${inv['amount']:,.2f}",
#                 #             "Invoice Status": inv["status"].replace("_", " ").title(),
#                 #             "Budget Result": inv["budget_result"].replace("_", " ").title(),
#                 #             "Remaining After Invoice": f"${inv['remaining_after_invoice']:,.2f}",
#                 #             "Needs Attention": "Yes" if inv["needs_attention"] else "No",
#                 #             "Review Reason": inv.get("validation_message") or "—",
#                 #             "_attention": inv["needs_attention"],
#                 #         }
#                 #     )
#                 rows = []
#                 for inv in matter["invoices"]:
#                     rows.append(
#                         {
#                             "Invoice No.": (
#                                 inv.get("invoice_no")
#                                 or f"#{inv['invoice_id']}"
#                             ),
#                             "Invoice Amount": (
#                                 f"${inv['amount']:,.2f}"
#                             ),
#                             "Invoice Status": (
#                                 inv["status"]
#                                 .replace("_", " ")
#                                 .title()
#                             ),
#                             "Budget Result": (
#                                 inv["budget_result"]
#                                 .replace("_", " ")
#                                 .title()
#                             ),
#                             "Projected Utilization": (
#                                 f"{float(inv.get('projected_utilization') or 0):.1f}%"
#                             ),
#                             "Remaining After Invoice": (
#                                 f"${float(inv['remaining_after_invoice']):,.2f}"
#                             ),
#                             "Needs Attention": (
#                                 "Yes"
#                                 if inv["needs_attention"]
#                                 else "No"
#                             ),
#                             "Review Reason": (
#                                 inv.get("validation_message")
#                                 or "—"
#                             ),
#                             "_attention": inv["needs_attention"],
#                         }
#                     )

#                 st.markdown("#### Related Invoices")
#                 if rows:
#                     df = pd.DataFrame(rows)
#                     display = df.drop(columns=["_attention"])

#                     def highlight_attention(row):
#                         return [
#                             "background-color: #ffe4e6; font-weight: 600" if rows[row.name]["_attention"] else ""
#                             for _ in row
#                         ]

#                     st.dataframe(
#                         display.style.apply(highlight_attention, axis=1),
#                         use_container_width=True,
#                         hide_index=True,
#                     )
#                     st.caption("Rows highlighted in red require budget attention. This remains reliable even with many invoices.")
#                 else:
#                     st.caption("No invoices are associated with this matter yet.")

#                 if user["role"] == "admin":
#                     st.markdown("#### Adjust Budget")
#                     attention_invoices = [
#                         inv for inv in matter["invoices"]
#                         if inv["status"] == "pending_review" and inv["needs_attention"]
#                     ]
#                     options = {"No specific invoice": None}
#                     for inv in attention_invoices:
#                         options[inv.get("invoice_no") or f"#{inv['invoice_id']}"] = inv["invoice_id"]

#                     with st.form(f"adjust_{matter['budget_id']}"):
#                         related_label = st.selectbox("Related invoice", list(options.keys()), key=f"rel_{matter['budget_id']}")
#                         amount = st.number_input(
#                             "Adjustment amount (+ increase / - decrease)",
#                             value=0.0,
#                             step=1000.0,
#                             key=f"amount_{matter['budget_id']}",
#                         )
#                         reason = st.text_area(
#                             "Reason for adjustment (required)",
#                             placeholder="Example: Additional litigation work approved.",
#                             key=f"reason_{matter['budget_id']}",
#                         )
#                         confirmed = st.checkbox(
#                             "I confirm this adjustment will be recorded in the audit log.",
#                             key=f"confirm_{matter['budget_id']}",
#                         )
#                         submitted = st.form_submit_button("Adjust budget", type="primary")

#                     if submitted:
#                         if amount == 0:
#                             st.error("Adjustment amount cannot be zero.")
#                         elif not reason.strip():
#                             st.error("A reason is required.")
#                         elif not confirmed:
#                             st.error("Please confirm the adjustment.")
#                         else:
#                             try:
#                                 result = client.adjust_budget(
#                                     matter["budget_id"],
#                                     amount,
#                                     reason,
#                                     confirmed,
#                                     options[related_label],
#                                 )
#                                 rec = result.get("reconciliation", {})
#                                 approved = rec.get("auto_approved", [])
#                                 pending = rec.get("still_pending", [])
#                                 flash(result.get("message", "Budget updated."), "success")
#                                 if approved:
#                                     flash(
#                                         "Auto-approved after budget reconciliation: "
#                                         + ", ".join(x.get("invoice_no") or f"#{x['invoice_id']}" for x in approved),
#                                         "success",
#                                     )
#                                 if pending:
#                                     flash(
#                                         f"{len(pending)} invoice(s) remain pending because non-budget review issues still exist.",
#                                         "warning",
#                                     )
#                                 st.rerun()
#                             except APIError as exc:
#                                 st.error(exc.detail)

#                 st.divider()