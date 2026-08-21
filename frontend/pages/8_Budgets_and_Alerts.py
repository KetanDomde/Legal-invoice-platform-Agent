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


# ============================================================================
# Page setup
# ============================================================================

st.set_page_config(
    page_title="Budgets & Alerts | Konverge",
    page_icon="💰",
    layout="wide",
)

inject_base_css()
sidebar_brand()
require_login()

client = get_client()
user = st.session_state["user"]


# ============================================================================
# Load budget hierarchy
#
# Backend returns:
#
# Firm
#   -> Matters
#       -> Budget
#       -> Related invoices
#       -> Budget status
# ============================================================================

try:
    hierarchy = client.get_budget_hierarchy()

except APIError as e:
    st.error(f"Couldn't load budget data: {e.detail}")
    st.stop()


# ============================================================================
# Calculate matters requiring attention
# ============================================================================

active_alerts = sum(
    1
    for firm in hierarchy
    for matter in firm["matters"]
    if matter["threshold_reached"] or matter["over_budget"]
)


# ============================================================================
# Page header
# ============================================================================

page_header(
    8,
    "Budgets & Alerts",
    (
        "Automatic budgets created from invoice intake. "
        "Firm → Matter → Invoice history and adjustments."
    ),
    extra_badge=badge(
        f"{active_alerts} matter(s) needing attention",
        "orange" if active_alerts else "green",
    ),
)


# ============================================================================
# Empty state
# ============================================================================

if not hierarchy:
    st.info(
        "No budget records yet. Upload an invoice with a matter identifier "
        "to automatically create the Firm, Matter and default $100,000 budget."
    )


# ============================================================================
# Firm -> Matter hierarchy
#
# IMPORTANT:
# Streamlit does not allow nested expanders.
#
# Therefore:
#
# Firm
#   -> Expander
#       -> Matter selector
#           -> Selected matter details
#               -> Invoices
#               -> Adjustment history
#               -> Budget adjustment
#
# This keeps the hierarchy clean without nesting expanders.
# ============================================================================

for firm in hierarchy:

    firm_name = firm.get("firm_name", "Unknown Firm")
    firm_address = firm.get("firm_address")
    firm_id = firm.get("firm_id")

    matters = firm.get("matters", [])

    # ------------------------------------------------------------------------
    # Firm header
    # ------------------------------------------------------------------------

    firm_title = f"🏢 {firm_name}"

    if firm_address:
        firm_title += f" — {firm_address}"

    # Only one level of expander is used.
    with st.expander(firm_title, expanded=True):

        # --------------------------------------------------------------------
        # Firm summary
        # --------------------------------------------------------------------

        total_invoices = sum(
            len(matter.get("invoices", []))
            for matter in matters
        )

        firm_attention_count = sum(
            1
            for matter in matters
            if matter.get("threshold_reached")
            or matter.get("over_budget")
        )

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Matters",
            len(matters),
        )

        col2.metric(
            "Invoices",
            total_invoices,
        )

        col3.metric(
            "Matters needing attention",
            firm_attention_count,
        )

        st.divider()

        # --------------------------------------------------------------------
        # No matters
        # --------------------------------------------------------------------

        if not matters:
            st.info(
                "No budget-enabled matters are available for this firm yet."
            )
            continue

        # --------------------------------------------------------------------
        # Matter selector
        #
        # We use a selectbox instead of another expander.
        # This avoids the Streamlit nested-expander exception.
        # --------------------------------------------------------------------

        matter_options = {
            matter["matter_id"]: (
                f"{matter.get('matter_no') or 'Matter'} - "
                f"{matter.get('matter_name') or 'Unnamed Matter'}"
            )
            for matter in matters
        }

        # If a matter is over budget or threshold reached,
        # make it the default selected matter.
        default_matter_id = next(
            (
                matter["matter_id"]
                for matter in matters
                if matter.get("over_budget")
                or matter.get("threshold_reached")
            ),
            matters[0]["matter_id"],
        )

        matter_ids = list(matter_options.keys())

        default_index = matter_ids.index(
            default_matter_id
        )

        selected_matter_id = st.selectbox(
            "Select matter",
            options=matter_ids,
            index=default_index,
            format_func=lambda matter_id: matter_options[matter_id],
            key=f"matter_selector_{firm_id}",
        )

        # Get the selected matter object.
        selected_matter = next(
            matter
            for matter in matters
            if matter["matter_id"] == selected_matter_id
        )

        matter_no = (
            selected_matter.get("matter_no")
            or "N/A"
        )

        matter_name = (
            selected_matter.get("matter_name")
            or "Unnamed Matter"
        )

        budget_id = selected_matter["budget_id"]

        # --------------------------------------------------------------------
        # Matter title
        # --------------------------------------------------------------------

        st.markdown(
            f"### {matter_no} - {matter_name}"
        )

        # --------------------------------------------------------------------
        # Budget metrics
        # --------------------------------------------------------------------

        effective_budget = float(
            selected_matter.get("allocated", 0)
        )

        utilized_amount = float(
            selected_matter.get("utilized", 0)
        )

        remaining_amount = float(
            selected_matter.get("remaining", 0)
        )

        utilization_percentage = float(
            selected_matter.get("pct_used", 0)
        )

        threshold_percentage = float(
            selected_matter.get("threshold_pct", 80)
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Effective budget",
            f"${effective_budget:,.2f}",
        )

        c2.metric(
            "Used",
            f"${utilized_amount:,.2f}",
        )

        c3.metric(
            "Remaining",
            f"${remaining_amount:,.2f}",
        )

        c4.metric(
            "Utilization",
            f"{utilization_percentage:.1f}%",
        )

        # --------------------------------------------------------------------
        # Budget progress
        # --------------------------------------------------------------------

        progress_value = min(
            max(utilization_percentage / 100, 0),
            1.0,
        )

        st.progress(
            progress_value,
            text=(
                f"Current utilization: "
                f"{utilization_percentage:.1f}% "
                f"| Alert threshold: "
                f"{threshold_percentage:.0f}%"
            ),
        )

        # --------------------------------------------------------------------
        # Budget status
        # --------------------------------------------------------------------

        if selected_matter.get("over_budget"):

            notice(
                (
                    "OVER BUDGET — This matter requires attention. "
                    "Review the related invoices and adjust the budget only "
                    "with a documented reason and confirmation."
                )
            )

        elif selected_matter.get("threshold_reached"):

            notice(
                (
                    "BUDGET THRESHOLD REACHED — Review the related invoices "
                    "and current budget position."
                )
            )

        else:

            notice(
                "Within budget threshold.",
                success=True,
            )

        st.divider()

        # ====================================================================
        # Related invoices
        # ====================================================================

        st.markdown("#### Related invoices")

        invoices = selected_matter.get(
            "invoices",
            [],
        )

        if invoices:

            invoice_rows = []

            for invoice in invoices:

                amount = float(
                    invoice.get("amount") or 0
                )

                remaining_after = (
                    invoice.get(
                        "remaining_after_invoice"
                    )
                )

                if remaining_after is not None:
                    remaining_after = float(
                        remaining_after
                    )

                attention_required = bool(
                    invoice.get(
                        "attention_required",
                        False,
                    )
                )

                budget_status = (
                    invoice.get(
                        "budget_status_at_intake"
                    )
                    or "N/A"
                )

                invoice_rows.append(
                    {
                        "Invoice No.": (
                            invoice.get("invoice_no")
                            or "N/A"
                        ),
                        "Invoice Amount": (
                            f"${amount:,.2f}"
                        ),
                        "Invoice Status": (
                            invoice.get("status")
                            or "N/A"
                        ),
                        "Budget Result": (
                            budget_status
                        ),
                        "Remaining After Invoice": (
                            (
                                f"${remaining_after:,.2f}"
                                if remaining_after is not None
                                else "N/A"
                            )
                        ),
                        "Needs Attention": (
                            "Yes"
                            if attention_required
                            else "No"
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
                "No invoices are associated with this matter yet."
            )

        st.divider()

        # ====================================================================
        # Budget adjustment
        #
        # Admin-only.
        #
        # Adjustment amount:
        #   +10000 = increase budget by $10,000
        #   -5000  = decrease budget by $5,000
        #
        # Backend validates:
        #   - Amount cannot be zero
        #   - Reason is mandatory
        #   - Confirmation is mandatory
        #   - Budget cannot become zero/negative
        #   - Audit log is created
        # ====================================================================

        if user.get("role") == "admin":

            st.markdown("#### Adjust budget")

            with st.form(
                f"adjust_budget_{budget_id}",
                clear_on_submit=True,
            ):

                adjustment_amount = st.number_input(
                    (
                        "Adjustment amount "
                        "(+ increase / - decrease)"
                    ),
                    value=0.0,
                    step=1000.0,
                    key=f"adjustment_amount_{budget_id}",
                    help=(
                        "Example: 25000 increases the budget by $25,000. "
                        "-10000 decreases the budget by $10,000."
                    ),
                )

                adjustment_reason = st.text_area(
                    "Reason for adjustment (required)",
                    key=f"adjustment_reason_{budget_id}",
                    placeholder=(
                        "Example: Additional litigation work approved."
                    ),
                )

                adjustment_confirmed = st.checkbox(
                    (
                        "I confirm this budget adjustment and understand "
                        "that it will be recorded in the audit log."
                    ),
                    key=f"adjustment_confirmed_{budget_id}",
                )

                submitted = st.form_submit_button(
                    "Adjust budget",
                    type="primary",
                )

                if submitted:

                    try:

                        client.adjust_budget(
                            budget_id,
                            adjustment_amount,
                            adjustment_reason,
                            adjustment_confirmed,
                        )

                        st.success(
                            (
                                "Budget adjusted successfully. "
                                "The adjustment history and audit log "
                                "have been updated."
                            )
                        )

                        st.rerun()

                    except APIError as e:

                        st.error(
                            f"Budget adjustment failed: {e.detail}"
                        )

        # ====================================================================
        # Adjustment history
        # ====================================================================

        try:

            adjustments = (
                client.list_budget_adjustments(
                    budget_id
                )
            )

            if adjustments:

                st.markdown(
                    "#### Budget adjustment history"
                )

                adjustment_rows = []

                for adjustment in adjustments:

                    previous_amount = float(
                        adjustment.get(
                            "previous_amount"
                        )
                        or 0
                    )

                    adjustment_amount = float(
                        adjustment.get(
                            "adjustment_amount"
                        )
                        or 0
                    )

                    new_amount = float(
                        adjustment.get(
                            "new_amount"
                        )
                        or 0
                    )

                    adjustment_rows.append(
                        {
                            "Type": (
                                adjustment.get(
                                    "adjustment_type"
                                )
                                or "N/A"
                            ),
                            "Previous Budget": (
                                f"${previous_amount:,.2f}"
                            ),
                            "Adjustment": (
                                f"${adjustment_amount:+,.2f}"
                            ),
                            "New Budget": (
                                f"${new_amount:,.2f}"
                            ),
                            "Reason": (
                                adjustment.get(
                                    "reason"
                                )
                                or "N/A"
                            ),
                            "Confirmed": (
                                "Yes"
                                if adjustment.get(
                                    "confirmed"
                                )
                                else "No"
                            ),
                            "Related Invoice ID": (
                                adjustment.get(
                                    "invoice_id"
                                )
                                or "N/A"
                            ),
                            "Created At": (
                                adjustment.get(
                                    "created_at"
                                )
                                or "N/A"
                            ),
                        }
                    )

                st.dataframe(
                    adjustment_rows,
                    use_container_width=True,
                    hide_index=True,
                )

            else:

                st.caption(
                    "No budget adjustments have been made yet."
                )

        except APIError:

            # Do not break the complete budget page if adjustment
            # history cannot be loaded for one matter.
            st.caption(
                "Adjustment history is currently unavailable."
            )