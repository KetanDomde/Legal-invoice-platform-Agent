import html
import re

import pandas as pd
import streamlit as st

from utils.theme import badge, inject_base_css, kv_row, notice, page_header, sidebar_brand
from utils.api_client import APIError, get_client, require_login
from utils.invoice_picker import pick_invoice

st.set_page_config(page_title="Matter & Budget Context | Konverge", page_icon="🏛️", layout="wide")

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
    # Prefer the backend's explicit alert classification. Message matching is
    # retained only as a backward-compatible fallback for older alert records.
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
    if any(x in value for x in ("over_budget", "over budget", "overrun", "exceed")):
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

inject_base_css()
sidebar_brand()
require_login()

client = get_client()
invoice = pick_invoice(label="Open Invoice")
if not invoice:
    st.stop()

try:
    hierarchy = client.get_budget_hierarchy() or []
    alerts = client.list_alerts(active_only=True) or []
except APIError as exc:
    st.error(f"Couldn't load matter and budget data: {exc.detail}")
    st.stop()

selected_firm = None
selected_matter = None
for firm in hierarchy:
    for matter in firm["matters"]:
        if matter["matter_id"] == invoice["matter_id"]:
            selected_firm = firm
            selected_matter = matter
            break
    if selected_matter:
        break

if not selected_matter:
    st.error("No budget context was found for this invoice's matter.")
    st.stop()

current_row = next(
    (row for row in selected_matter["invoices"] if row["invoice_id"] == invoice["invoice_id"]),
    None,
)

page_header(
    4,
    "Matter & Budget Context",
    "Matter, firm, invoice impact, current budget position, and actionable alerts in one place.",
    extra_badge=badge(
        "Attention Required" if current_row and current_row["needs_attention"] else "Budget Checked",
        "orange" if current_row and current_row["needs_attention"] else "green",
    ),
)

left, right = st.columns([3.1, 1])

with right:
    with st.container(border=True):
        st.markdown("#### 🔔 Alerts")
        matter_alerts = [
            a for a in alerts
            if a["budget_id"] == selected_matter["budget_id"]
        ]
        if matter_alerts:
            st.caption(
                f"{len(matter_alerts)} active alert"
                f"{'s' if len(matter_alerts) != 1 else ''} · scroll to view all"
            )
            # Use a native Streamlit scroll container so multiple alerts stay
            # inside the right rail and never push the main content downward.
            with st.container(height=520, border=False):
                for alert in matter_alerts:
                    render_budget_alert(alert)
        else:
            st.success("No active alerts for this matter.")

with left:
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("#### Firm")
            kv_row("Firm Name", selected_firm["firm_name"])
            kv_row("Firm ID", selected_firm["firm_id"])
            kv_row("Address", selected_firm.get("firm_address") or "—")
    with c2:
        with st.container(border=True):
            st.markdown("#### Matter")
            kv_row("Matter ID", selected_matter.get("matter_no") or str(selected_matter["matter_id"]))
            kv_row("Matter Name", selected_matter["matter_name"])
            kv_row("Internal Matter Record", f"#{selected_matter['matter_id']}")

    st.markdown("## Budget Decision")
    if current_row:
        d1, d2, d3, d4 = st.columns(4)

        invoice_amount = float(current_row.get("amount") or 0)
        effective_budget = float(selected_matter.get("allocated") or 0)
        invoice_status = str(invoice.get("status") or current_row.get("status") or "").lower()

        # Pending invoices are projected against today's approved spend. Once
        # an invoice is approved after a budget adjustment, the displayed
        # decision must switch to the current ledger-backed budget position
        # instead of showing the stale intake snapshot.
        if invoice_status == "pending_review":
            projected_remaining = float(current_row.get("remaining_after_invoice") or 0)
            projected_utilization = current_row.get("projected_utilization")
            if projected_utilization is None and effective_budget > 0:
                projected_utilization = (
                    (float(selected_matter.get("utilized") or 0) + invoice_amount)
                    / effective_budget
                ) * 100
            current_result = current_row.get("budget_result") or "within_budget"
        else:
            projected_remaining = float(selected_matter.get("remaining") or 0)
            projected_utilization = float(selected_matter.get("pct_used") or 0)
            if selected_matter.get("over_budget"):
                current_result = "over_budget"
            elif selected_matter.get("threshold_reached"):
                current_result = "threshold_reached"
            else:
                current_result = "within_budget"

        d1.metric("Invoice Amount", f"${invoice_amount:,.2f}")
        d2.metric("Effective Budget", f"${effective_budget:,.2f}")
        d3.metric("Projected Remaining", f"${projected_remaining:,.2f}")
        d4.metric(
            "Projected Utilization",
            f"{float(projected_utilization):.1f}%"
            if projected_utilization is not None
            else "—",
        )

        if current_result == "over_budget":
            notice(
                "OVER BUDGET — this invoice cannot clear the budget gate until "
                "the budget is adjusted or an authorized override is used."
            )
        elif current_result == "threshold_reached":
            notice(
                "BUDGET THRESHOLD REACHED — warning only. The invoice may still "
                "be approved if all other validation checks pass."
            )
        else:
            notice("WITHIN BUDGET — no budget blocker is present.", success=True)

        if invoice_status == "pending_review" and current_row.get("validation_message"):
            st.markdown("#### Why This Invoice Is Pending / What To Resolve")
            for reason in [
                x.strip()
                for x in current_row["validation_message"].split(";")
                if x.strip()
            ]:
                st.warning(reason)

        if current_row.get("intake_budget_result"):
            st.caption(
                f"Historical intake snapshot: "
                f"{current_row['intake_budget_result'].replace('_', ' ').title()}"
                + (
                    f" · remaining after intake "
                    f"${current_row['intake_remaining_after_invoice']:,.2f}"
                    if current_row.get("intake_remaining_after_invoice") is not None
                    else ""
                )
            )

    st.markdown("## Related Invoices for This Matter")
    rows = []
    for row in selected_matter["invoices"]:
        rows.append({
            "Invoice No.": row.get("invoice_no") or f"#{row['invoice_id']}",
            "Amount": f"${row['amount']:,.2f}",
            "Status": row["status"].replace("_", " ").title(),
            "Budget Result": row["budget_result"].replace("_", " ").title(),
            "Remaining After Invoice": f"${row['remaining_after_invoice']:,.2f}",
            "Needs Attention": "Yes" if row["needs_attention"] else "No",
            "Current Invoice": "Yes" if row["invoice_id"] == invoice["invoice_id"] else "",
            "_attention": row["needs_attention"],
        })
    df = pd.DataFrame(rows)
    display = df.drop(columns=["_attention"])

    def highlight(row):
        attention = rows[row.name]["_attention"]
        return ["background-color: #ffe4e6; font-weight: 600" if attention else "" for _ in row]

    st.dataframe(display.style.apply(highlight, axis=1), use_container_width=True, hide_index=True)

    st.markdown("## Budget Activity")
    try:
        adjustments = client.list_budget_adjustments(selected_matter["budget_id"]) or []
        ledger = client.list_budget_ledger(budget_id=selected_matter["budget_id"]) or []
    except APIError as exc:
        adjustments, ledger = [], []
        st.warning(f"Couldn't load budget activity: {exc.detail}")

    invoice_names = {r["invoice_id"]: r.get("invoice_no") or f"#{r['invoice_id']}" for r in selected_matter["invoices"]}
    activity = []
    for item in adjustments:
        activity.append({
            "created_at": item["created_at"],
            "Activity": f"Budget {item['adjustment_type'].title()}",
            "Invoice": item.get("invoice_no") or "—",
            "Amount / Change": f"${item['adjustment_amount']:+,.2f}",
            "Budget After": f"${item['new_amount']:,.2f}",
            "Reason": item["reason"],
            "Confirmed": "Yes" if item["confirmed"] else "No",
        })
    for item in ledger:
        activity.append({
            "created_at": item["created_at"],
            "Activity": "Invoice Approved",
            "Invoice": invoice_names.get(item["invoice_id"], f"#{item['invoice_id']}"),
            "Amount / Change": f"${item['amount']:,.2f}",
            "Budget After": "—",
            "Reason": "—",
            "Confirmed": "—",
        })
    if activity:
        activity.sort(key=lambda x: str(x["created_at"]), reverse=True)
        activity_df = pd.DataFrame(activity).drop(columns=["created_at"])
        st.dataframe(activity_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No budget activity recorded yet.")

if st.button("Continue to Validation & Duplicate Check →", type="primary"):
    st.switch_page("pages/5_Validation_Check.py")