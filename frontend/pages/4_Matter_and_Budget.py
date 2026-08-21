import streamlit as st

from utils.theme import (
    badge,
    inject_base_css,
    kv_row,
    notice,
    page_header,
    sidebar_brand,
    status_badge,
)
from utils.api_client import (
    get_client,
    require_login,
    APIError,
)
from utils.invoice_picker import pick_invoice


# ============================================================================
# Page setup
# ============================================================================

st.set_page_config(
    page_title="Matter & Budget Context | Konverge",
    page_icon="🏛️",
    layout="wide",
)

inject_base_css()
sidebar_brand()
require_login()

client = get_client()


# ============================================================================
# Select invoice
# ============================================================================

invoice = pick_invoice(
    label="Open Invoice"
)

if not invoice:
    st.stop()


# ============================================================================
# Load one complete invoice-level budget context from the backend.
#
# IMPORTANT:
# This page intentionally uses one backend endpoint instead of independently
# loading firms, matters, budgets, summaries, ledger entries and alerts.
#
# This prevents the frontend from duplicating budget calculations.
# ============================================================================

try:
    context = client.get_invoice_budget_context(
        invoice["invoice_id"]
    )

except APIError as e:
    st.error(
        f"Couldn't load invoice budget context: {e.detail}"
    )
    st.stop()


invoice_data = context["invoice"]
firm = context["firm"]
matter = context["matter"]
budget = context["budget"]

intake_snapshot = context.get(
    "intake_snapshot",
    {}
)

related_invoices = context.get(
    "related_invoices",
    []
)

budget_activity = context.get(
    "budget_activity",
    []
)

alerts = context.get(
    "alerts",
    [])


# ============================================================================
# Helper functions
# ============================================================================

def money(value):
    """
    Format money consistently across this page.
    """

    if value is None:
        return "—"

    return f"${float(value):,.2f}"


def format_status(value):
    """
    Convert backend values such as:
        threshold_reached
        over_budget

    into:
        Threshold Reached
        Over Budget
    """

    if not value:
        return "—"

    return str(value).replace(
        "_",
        " "
    ).title()


def budget_status_badge(status_value):
    """
    Return a clean badge for budget status.
    """

    if status_value == "over_budget":
        return badge(
            "Over Budget",
            "red",
        )

    if status_value == "threshold_reached":
        return badge(
            "Threshold Reached",
            "orange",
        )

    if status_value == "within_budget":
        return badge(
            "Within Budget",
            "green",
        )

    if status_value == "no_budget":
        return badge(
            "No Budget",
            "gray",
        )

    return badge(
        format_status(status_value),
        "gray",
    )


# ============================================================================
# Page header
# ============================================================================

page_header(
    4,
    "Matter & Budget Context",
    (
        "Invoice-level budget impact, firm and matter context, "
        "related invoices, and budget activity."
    ),
    extra_badge=budget_status_badge(
        budget.get("projected_status")
        or intake_snapshot.get("status")
    ),
)


# ============================================================================
# Top section
#
# Left  -> current invoice
# Right -> projected budget impact
# ============================================================================

left, right = st.columns(
    [1.25, 1]
)


with left:
    with st.container(border=True):

        st.markdown(
            "#### Current Invoice"
        )

        kv_row(
            "Invoice No.",
            invoice_data.get("invoice_no")
            or f"#{invoice_data['invoice_id']}",
        )

        kv_row(
            "Invoice Amount",
            money(
                invoice_data.get(
                    "total_amount"
                )
            ),
        )

        kv_row(
            "Invoice Date",
            invoice_data.get(
                "invoice_date"
            )
            or "—",
        )

        billing_start = invoice_data.get(
            "billing_period_start"
        )

        billing_end = invoice_data.get(
            "billing_period_end"
        )

        if billing_start or billing_end:
            kv_row(
                "Billing Period",
                (
                    f"{billing_start or '—'} "
                    f"to {billing_end or '—'}"
                ),
            )

        kv_row(
            "Current Status",
            status_badge(
                invoice_data.get(
                    "status",
                    "submitted",
                )
            ),
        )

        kv_row(
            "Invoice ID",
            f"#{invoice_data['invoice_id']}",
        )


with right:
    with st.container(border=True):

        st.markdown(
            "#### Budget Impact"
        )

        if budget.get("has_budget"):

            projected_pct = float(
                budget.get(
                    "projected_pct_used",
                    0,
                )
            )

            st.progress(
                min(
                    max(
                        projected_pct / 100,
                        0,
                    ),
                    1.0,
                ),
                text=(
                    f"Projected utilization: "
                    f"{projected_pct:.1f}%"
                ),
            )

            kv_row(
                "Effective Budget",
                money(
                    budget.get(
                        "allocated"
                    )
                ),
            )

            kv_row(
                "Already Used",
                money(
                    budget.get(
                        "utilized"
                    )
                ),
            )

            kv_row(
                "Remaining Before Invoice",
                money(
                    budget.get(
                        "remaining"
                    )
                ),
            )

            kv_row(
                "Current Invoice",
                money(
                    budget.get(
                        "invoice_amount"
                    )
                ),
            )

            kv_row(
                "Projected Remaining",
                money(
                    budget.get(
                        "projected_remaining"
                    )
                ),
            )

            kv_row(
                "Alert Threshold",
                (
                    f"{float(budget.get('threshold_pct', 0)):.0f}%"
                ),
            )

        else:

            st.warning(
                "No budget is available for this matter."
            )


# ============================================================================
# Firm and matter identity
#
# Matter No. is intentionally displayed separately from the matter name.
# The business identifier is important because:
#
# Same Firm + Same Matter ID = Same Matter
# ============================================================================

st.markdown(
    "### Firm & Matter Context"
)

context_left, context_right = st.columns(
    2
)


with context_left:
    with st.container(border=True):

        st.markdown(
            "#### Firm"
        )

        kv_row(
            "Firm Name",
            firm.get("name")
            or "—",
        )

        kv_row(
            "Firm ID",
            firm.get("firm_id")
            or "—",
        )

        kv_row(
            "Address",
            firm.get("address")
            or "—",
        )


with context_right:
    with st.container(border=True):

        st.markdown(
            "#### Matter"
        )

        kv_row(
            "Matter ID",
            matter.get("matter_no")
            or "—",
        )

        kv_row(
            "Matter Name",
            matter.get("name")
            or "—",
        )

        kv_row(
            "Internal Matter Record",
            f"#{matter['matter_id']}",
        )

        kv_row(
            "Owner",
            matter.get("owner")
            or "Unassigned",
        )

        kv_row(
            "Matter Status",
            format_status(
                matter.get("status")
            ),
        )


# ============================================================================
# Budget decision
#
# The current invoice may not yet be approved.
#
# Therefore:
#   Actual budget = approved ledger entries
#   Projected budget = actual budget + current invoice
#
# If the invoice is already posted, the backend prevents double counting.
# ============================================================================

st.markdown(
    "### Budget Decision"
)

projected_status = budget.get(
    "projected_status"
)

if not budget.get("has_budget"):

    st.error(
        (
            "NO BUDGET — This invoice cannot be approved until "
            "a valid budget is available for this matter."
        )
    )

elif projected_status == "over_budget":

    over_by = abs(
        float(
            budget.get(
                "projected_remaining",
                0,
            )
        )
    )

    st.error(
        (
            "OVER BUDGET — If this invoice proceeds without a budget "
            f"adjustment, the matter will exceed its budget by "
            f"{money(over_by)}."
        )
    )

    st.caption(
        (
            "Review the invoice and budget in Budgets & Alerts. "
            "An Admin can adjust the budget with a mandatory reason "
            "and confirmation."
        )
    )

    if st.button(
        "Go to Budgets & Alerts →",
        type="primary",
    ):
        st.switch_page(
            "pages/8_Budgets_and_Alerts.py"
        )

elif projected_status == "threshold_reached":

    st.warning(
        (
            "BUDGET THRESHOLD REACHED — This invoice does not exceed "
            "the total budget, but it reaches or crosses the configured "
            f"{float(budget.get('threshold_pct', 0)):.0f}% threshold."
        )
    )

    st.caption(
        (
            "Budget attention is recommended before the invoice "
            "continues through the workflow."
        )
    )

elif budget.get("already_posted"):

    st.success(
        (
            "This invoice has already been posted to the approved "
            "budget ledger. The figures above show the current actual "
            "budget position without counting this invoice twice."
        )
    )

else:

    st.success(
        (
            "WITHIN BUDGET — The projected impact of this invoice "
            "remains below the configured alert threshold."
        )
    )


# ============================================================================
# Intake snapshot
#
# This preserves the budget position that existed when the invoice first
# entered the system.
#
# It is intentionally separate from the current budget because the budget
# may have been adjusted later.
# ============================================================================

if intake_snapshot:

    st.markdown(
        "### Budget Position at Intake"
    )

    snapshot_left, snapshot_right = st.columns(
        2
    )

    with snapshot_left:
        with st.container(border=True):

            kv_row(
                "Budget at Intake",
                money(
                    intake_snapshot.get(
                        "budget_amount"
                    )
                ),
            )

            kv_row(
                "Used Before Invoice",
                money(
                    intake_snapshot.get(
                        "used_before_invoice"
                    )
                ),
            )

            kv_row(
                "Projected After Invoice",
                money(
                    intake_snapshot.get(
                        "projected_after_invoice"
                    )
                ),
            )

    with snapshot_right:
        with st.container(border=True):

            kv_row(
                "Remaining After Invoice",
                money(
                    intake_snapshot.get(
                        "remaining_after_invoice"
                    )
                ),
            )

            projected_pct = intake_snapshot.get(
                "projected_pct"
            )

            kv_row(
                "Projected Utilization",
                (
                    f"{float(projected_pct):.1f}%"
                    if projected_pct is not None
                    else "—"
                ),
            )

            kv_row(
                "Initial Budget Result",
                budget_status_badge(
                    intake_snapshot.get(
                        "status"
                    )
                ),
            )

            kv_row(
                "Attention Required",
                (
                    "Yes"
                    if intake_snapshot.get(
                        "attention_required"
                    )
                    else "No"
                ),
            )


# ============================================================================
# Related invoices
#
# All invoices belonging to the same Firm + Matter ID budget are shown here.
# ============================================================================

st.markdown(
    "### Related Invoices for This Matter"
)

st.caption(
    (
        f"Firm: {firm.get('name', '—')}  |  "
        f"Matter: {matter.get('matter_no', '—')} - "
        f"{matter.get('name', '—')}"
    )
)

if related_invoices:

    invoice_rows = []

    for related in related_invoices:

        invoice_rows.append(
            {
                "Invoice No.": (
                    related.get("invoice_no")
                    or f"#{related['invoice_id']}"
                ),
                "Amount": money(
                    related.get(
                        "total_amount"
                    )
                ),
                "Status": format_status(
                    related.get(
                        "status"
                    )
                ),
                "Intake Budget Result": format_status(
                    related.get(
                        "budget_status_at_intake"
                    )
                ),
                "Remaining After Intake": money(
                    related.get(
                        "budget_remaining_after_invoice"
                    )
                ),
                "Needs Attention": (
                    "Yes"
                    if related.get(
                        "budget_attention_required"
                    )
                    else "No"
                ),
                "Current Invoice": (
                    "Yes"
                    if related.get(
                        "is_current"
                    )
                    else ""
                ),
            }
        )

    st.dataframe(
        invoice_rows,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.caption(
        "No related invoices were found."
    )


# ============================================================================
# Budget activity
#
# This replaces the old technical "Budget Ledger Evidence" presentation.
#
# The user sees business-friendly events:
#   - Invoice approved
#   - Budget increased
#   - Budget decreased
# ============================================================================

st.markdown(
    "### Budget Activity"
)

if budget_activity:

    activity_rows = []

    for activity in budget_activity:

        activity_rows.append(
            {
                "Date": activity.get(
                    "created_at"
                )
                or "—",
                "Activity": format_status(
                    activity.get(
                        "activity_type"
                    )
                ),
                "Invoice": (
                    activity.get(
                        "invoice_no"
                    )
                    or "—"
                ),
                "Amount / Change": money(
                    activity.get(
                        "amount"
                    )
                ),
                "Budget After": money(
                    activity.get(
                        "budget_after"
                    )
                ),
                "Reason": (
                    activity.get(
                        "reason"
                    )
                    or "—"
                ),
                "Confirmed": (
                    "Yes"
                    if activity.get(
                        "confirmed"
                    ) is True
                    else (
                        "No"
                        if activity.get(
                            "confirmed"
                        ) is False
                        else "—"
                    )
                ),
            }
        )

    st.dataframe(
        activity_rows,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.caption(
        "No approved invoice or budget adjustment activity yet."
    )


# ============================================================================
# Alerts
# ============================================================================

if alerts:

    st.markdown(
        "### Budget Alerts"
    )

    for alert in alerts:

        message = alert.get(
            "message"
        ) or "Budget attention required."

        if alert.get(
            "is_active",
            True,
        ):
            st.warning(
                message
            )
        else:
            st.info(
                message
            )


# ============================================================================
# Continue workflow
# ============================================================================

st.markdown("---")

if st.button(
    "Continue to Validation & Duplicate Check →",
    type="primary",
):

    st.session_state[
        "selected_invoice_id"
    ] = invoice_data["invoice_id"]

    st.switch_page(
        "pages/5_Validation_Check.py"
    )