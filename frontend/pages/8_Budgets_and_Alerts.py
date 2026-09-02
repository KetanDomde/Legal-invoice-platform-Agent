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

def _alert_firm_names(active_alerts: list[dict]) -> set[str]:
    """Return normalized firm names that have active alerts."""
    return {
        str(alert.get("firm_name") or "").strip().lower()
        for alert in active_alerts
        if alert.get("firm_name")
    }


def _matter_budget_view(matter: dict) -> tuple[float, float, float, float, bool, bool]:
    """Return projected budget values while preserving approved-spend as actual."""
    allocated = float(matter.get("allocated") or 0)
    approved = float(matter.get("utilized") or 0)

    # New backend fields include all pending-review invoice impact.
    # Fall back to approved values if an older backend is being used.
    projected = float(matter.get("projected_utilized", approved) or approved)
    projected_remaining = float(
        matter.get("projected_remaining", allocated - projected)
        if matter.get("projected_remaining") is not None
        else allocated - projected
    )
    projected_pct = float(
        matter.get(
            "projected_pct_used",
            (projected / allocated * 100) if allocated else 0,
        )
        or 0
    )
    projected_threshold = bool(
        matter.get(
            "projected_threshold_reached",
            projected_pct >= float(matter.get("threshold_pct") or 0),
        )
    )
    projected_over = bool(
        matter.get("projected_over_budget", projected > allocated)
    )
    return (
        allocated,
        approved,
        projected_remaining,
        projected_pct,
        projected_threshold,
        projected_over,
    )


# Incremented after a successful budget adjustment so Streamlit creates a fresh
# form instance instead of restoring the previous widget values.
if "budget_adjust_form_version" not in st.session_state:
    st.session_state["budget_adjust_form_version"] = 0

client = get_client()
user = st.session_state["user"]

try:
    hierarchy = client.get_budget_hierarchy() or []
    active_alerts = client.list_alerts(active_only=True) or []
except APIError as exc:
    st.error(f"Couldn't load budget data: {exc.detail}")
    st.stop()

adjustment_result = st.session_state.pop("budget_adjustment_result", None)
if adjustment_result:
    if adjustment_result["type"] == "warning":
        st.warning(adjustment_result["message"])
    else:
        st.success(adjustment_result["message"])


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

    alert_firm_names = _alert_firm_names(active_alerts)

    for firm in hierarchy:
        # Open firms that either contain an invoice requiring attention OR
        # are directly referenced by an active budget alert.
        firm_name = firm.get("firm_name")
        invoice_needs_attention = any(
            inv.get("needs_attention", False)
            for matter in firm.get("matters", [])
            for inv in matter.get("invoices", [])
        )
        firm_has_active_alert = (
            str(firm_name or "").strip().lower() in alert_firm_names
        )
        firm_needs_attention = invoice_needs_attention or firm_has_active_alert

        with st.expander(
            f"🏢 {firm['firm_name']}  ·  {len(firm['matters'])} matter(s)",
            expanded=firm_needs_attention,
        ):
            if firm.get("firm_address"):
                st.caption(firm["firm_address"])

            for matter in firm["matters"]:
                title = f"{matter.get('matter_no') or 'Matter'} — {matter['matter_name']}"
                st.markdown(f"### {title}")

                (
                    allocated,
                    approved,
                    projected_remaining,
                    projected_pct,
                    projected_threshold,
                    projected_over,
                ) = _matter_budget_view(matter)

                pending_amount = float(matter.get("pending_invoice_amount") or 0)
                pending_count = int(matter.get("pending_invoice_count") or 0)
                has_pending_impact = pending_count > 0 and pending_amount > 0

                # Keep the existing metric names. Approved spend remains the
                # actual ledger-backed approved spend; Remaining and Utilization
                # reflect pending-review invoice impact when applicable.
                display_remaining = projected_remaining if has_pending_impact else float(matter.get("remaining") or allocated - approved)
                display_pct = projected_pct if has_pending_impact else float(matter.get("pct_used") or 0)
                display_over = projected_over if has_pending_impact else bool(matter.get("over_budget"))
                display_threshold = projected_threshold if has_pending_impact else bool(matter.get("threshold_reached"))

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Effective budget", f"${allocated:,.2f}")
                m2.metric("Approved spend", f"${approved:,.2f}")
                m3.metric("Remaining", f"${display_remaining:,.2f}")
                m4.metric("Utilization", f"{display_pct:.1f}%")

                progress_text = (
                    f"Projected utilization: {display_pct:.1f}% · "
                    f"Alert threshold: {float(matter.get('threshold_pct') or 0):.0f}%"
                    if has_pending_impact
                    else
                    f"Current utilization: {display_pct:.1f}% · "
                    f"Alert threshold: {float(matter.get('threshold_pct') or 0):.0f}%"
                )
                if has_pending_impact:
                    progress_text += (
                        f" · Pending review: ${pending_amount:,.2f}"
                        f" ({pending_count} invoice{'s' if pending_count != 1 else ''})"
                    )

                st.progress(
                    min(display_pct / 100, 1.0),
                    text=progress_text,
                )

                if display_over:
                    notice(
                        "OVER BUDGET — pending/approved invoice impact is above the effective budget."
                        if has_pending_impact
                        else "OVER BUDGET — the approved spend is above the effective budget."
                    )
                elif display_threshold:
                    notice(
                        "Budget threshold reached based on projected spend including pending-review invoices."
                        if has_pending_impact
                        else "Budget threshold reached. This is a warning; it does not by itself block approval."
                    )
                else:
                    notice("Within the configured budget threshold.", success=True)

                rows = []
                for inv in matter["invoices"]:
                    rows.append(
                        {
                            "Invoice No.": inv.get("invoice_no") or f"#{inv['invoice_id']}",
                            "Invoice Amount": f"${inv['amount']:,.2f}",
                            "Invoice Status": inv["status"].replace("_", " ").title(),
                            "Budget Result": inv["budget_result"].replace("_", " ").title(),
                            "Remaining After Invoice": f"${inv.get('remaining_after_invoice', 0):,.2f}",
                            "Needs Attention": "Yes" if inv.get("needs_attention", False) else "No",
                            "Review Reason": inv.get("validation_message") or "—",
                            "_attention": inv.get("needs_attention", False),
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
                    # A budget adjustment should be tied to a specific invoice.
                    # Keep a placeholder instead of allowing "No specific invoice"
                    # to be submitted accidentally.
                    options = {"Select an invoice": None}
                    for inv in attention_invoices:
                        options[inv.get("invoice_no") or f"#{inv['invoice_id']}"] = inv["invoice_id"]

                    form_version = st.session_state["budget_adjust_form_version"]
                    form_key = f"adjust_{matter['budget_id']}_{form_version}"

                    with st.form(form_key):
                        related_label = st.selectbox(
                            "Related invoice",
                            list(options.keys()),
                            key=f"rel_{matter['budget_id']}_{form_version}",
                        )
                        amount = st.number_input(
                            "Adjustment amount (+ increase / - decrease)",
                            value=0.0,
                            step=1000.0,
                            key=f"amount_{matter['budget_id']}_{form_version}",
                        )
                        reason = st.text_area(
                            "Reason for adjustment (required)",
                            placeholder="Example: Additional litigation work approved.",
                            key=f"reason_{matter['budget_id']}_{form_version}",
                        )
                        confirmed = st.checkbox(
                            "I confirm this adjustment will be recorded in the audit log.",
                            key=f"confirm_{matter['budget_id']}_{form_version}",
                        )

                        # Keep the button disabled until all required inputs are valid.
                        # Confirmation is also required because the backend expects it.
                        form_ready = (
                            options.get(related_label) is not None
                            and amount != 0
                            and bool(reason.strip())
                            and confirmed
                        )

                        submitted = st.form_submit_button(
                            "Adjust budget",
                            type="primary",
                            disabled=not form_ready,
                        )

                    if not form_ready:
                        st.caption(
                            "Select an invoice, enter a non-zero adjustment amount, "
                            "provide a reason, and confirm the audit-log entry to enable Adjust budget."
                        )

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
                                    reason,
                                    confirmed,
                                    options[related_label],
                                )
                                rec = result.get("reconciliation", {})
                                approved = rec.get("auto_approved", [])
                                pending = rec.get("still_pending", [])

                                message = result.get("message", "Budget updated successfully.")
                                if approved:
                                    approved_numbers = ", ".join(
                                        x.get("invoice_no") or f"#{x['invoice_id']}"
                                        for x in approved
                                    )
                                    message += (
                                        f" Invoice {approved_numbers} was approved successfully "
                                        "after budget reconciliation."
                                    )
                                elif pending:
                                    message += (
                                        f" {len(pending)} invoice(s) remain pending because "
                                        "non-budget review issues still exist."
                                    )

                                st.session_state["budget_adjustment_result"] = {
                                    "message": message,
                                    "type": "success" if approved or not pending else "warning",
                                }

                                # Change the form identity before rerunning. Streamlit
                                # will create fresh widgets, so the previous amount/reason/
                                # confirmation cannot be restored or submitted again.
                                st.session_state["budget_adjust_form_version"] += 1

                                st.rerun()
                            except APIError as exc:
                                st.error(exc.detail)

                st.divider()