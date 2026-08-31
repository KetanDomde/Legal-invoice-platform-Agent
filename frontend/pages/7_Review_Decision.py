import streamlit as st

from utils.theme import (
    inject_base_css,
    kv_row,
    notice,
    page_header,
    sidebar_brand,
    status_badge,
)
from utils.api_client import (
    get_client,
    require_role,
    APIError,
)
from utils.invoice_picker import pick_invoice
from utils.notifications import flash


st.set_page_config(
    page_title="Review Decision | Konverge",
    page_icon="✅",
    layout="wide",
)

inject_base_css()
sidebar_brand()

# ---------------------------------------------------------
# RBAC
# ---------------------------------------------------------

require_role("admin", "editor")

client = get_client()


# ---------------------------------------------------------
# Select invoice
# ---------------------------------------------------------

invoice = pick_invoice(
    label="Invoice to Decide"
)

if not invoice:
    st.stop()


# ---------------------------------------------------------
# Load latest review information
# ---------------------------------------------------------

try:
    review_inv = client.get_review_invoice(
        invoice["invoice_id"]
    )

    # IMPORTANT:
    # Always use the latest backend state.
    invoice = review_inv

except APIError as e:
    review_inv = None

    st.warning(
        (
            "Couldn't load review-queue context "
            f"(it may already be decided): {e.detail}"
        )
    )


# ---------------------------------------------------------
# Budget information
# ---------------------------------------------------------

try:
    budget_summaries = client.list_budget_summaries()

    budget_summary = next(
        (
            summary
            for summary in budget_summaries
            if summary["matter_id"]
            == invoice["matter_id"]
        ),
        None,
    )

except APIError:
    budget_summary = None


# ---------------------------------------------------------
# Page Header
# ---------------------------------------------------------

page_header(
    7,
    "Review & Decision",
    (
        "Review the invoice context and make a human "
        "decision. Approval is always revalidated by "
        "the backend."
    ),
    extra_badge=status_badge(
        invoice["status"]
    ),
)


left, right = st.columns([2, 1])


# =========================================================
# LEFT SIDE - INVOICE CONTEXT
# =========================================================

with left:

    with st.container(border=True):

        st.markdown(
            "#### Invoice Context"
        )

        kv_row(
            "Invoice",
            invoice.get("invoice_no")
            or f"#{invoice['invoice_id']}",
        )

        kv_row(
            "Matter",
            invoice.get("matter_id")
            or "—",
        )

        kv_row(
            "Amount",
            (
                f"${invoice['total_amount']:,.2f}"
                if invoice.get("total_amount")
                is not None
                else "—"
            ),
        )

        kv_row(
            "Confidence",
            (
                f"{invoice['confidence_score']:.0%}"
                if invoice.get("confidence_score")
                is not None
                else "—"
            ),
        )

        kv_row(
            "Budget Valid",
            (
                "Yes"
                if invoice.get("budget_valid") is True
                else (
                    "No"
                    if invoice.get("budget_valid") is False
                    else "—"
                )
            ),
        )

        kv_row(
            "Possible Duplicate",
            (
                "Yes"
                if invoice.get("duplicate_flag")
                else "No"
            ),
        )

        kv_row(
            "Validation",
            (
                invoice.get("validation_status")
                or "—"
            ),
        )

        # -------------------------------------------------
        # Budget summary
        # -------------------------------------------------

        if budget_summary:

            kv_row(
                "Current Utilization",
                f"{budget_summary['pct_used']:.1f}%",
            )

            kv_row(
                "Current Remaining",
                (
                    f"${budget_summary['remaining']:,.2f}"
                ),
            )


        # -------------------------------------------------
        # Review reasons
        # -------------------------------------------------

        if (
            review_inv
            and review_inv.get("review_reasons")
        ):

            st.markdown(
                "#### Why This Needs Review"
            )

            for reason in review_inv[
                "review_reasons"
            ]:
                st.warning(reason)


        # -------------------------------------------------
        # Validation message
        # -------------------------------------------------

        if invoice.get("validation_message"):

            st.markdown(
                "#### Validation Result"
            )

            st.info(
                invoice["validation_message"]
            )


        # -------------------------------------------------
        # Already completed
        # -------------------------------------------------

        if invoice["status"] in (
            "approved",
            "rejected",
        ):

            notice(
                (
                    f"This invoice is already "
                    f"**{invoice['status'].replace('_', ' ').title()}**."
                )
            )
# =========================================================
# RIGHT SIDE - DECISION
# =========================================================

with right:
    with st.container(border=True):
        st.markdown(
            "#### Decision"
        )

        if invoice["status"] == "clarification_requested":
            # Paused workflow: the only path forward is answering the
            # reviewer's question. The server re-validates and returns
            # the invoice to pending_review once information is provided.
            st.info(
                "This invoice is paused awaiting clarification. "
                "Submit the requested information to send it back to the review queue."
            )

            info_text = st.text_area(
                "Clarification response (required)"
            )

            if st.button(
                "Submit Information",
                type="primary",
                disabled=not bool(info_text.strip()),
            ):
                try:
                    client.provide_information(
                        invoice["invoice_id"],
                        info=info_text.strip(),
                    )
                    flash(
                        "Clarification received — invoice returned to the review queue.",
                        "success",
                    )
                    st.rerun()
                except APIError as e:
                    st.error(e.detail)

        elif invoice["status"] == "pending_review":
            no_budget = (
                budget_summary is None
                or not budget_summary.get(
                    "has_budget",
                    False,
                )
            )

            over_budget = False

            if budget_summary:
                projected_utilized = (
                    budget_summary["utilized"]
                    + float(
                        invoice.get(
                            "total_amount",
                            0,
                        )
                        or 0
                    )
                )

                over_budget = (
                    projected_utilized
                    > budget_summary["allocated"]
                )

            action = st.radio(
                "Action",
                [
                    "Approve",
                    "Reject",
                    "Ask for Clarification",
                ],
                horizontal=False,
            )

            approval_blocked = (
                action == "Approve"
                and (no_budget or over_budget)
            )

            if action == "Approve" and no_budget:
                st.error(
                    "This matter has no configured budget. "
                    "Approval is blocked until a budget is created."
                )

            if action == "Approve" and over_budget and not no_budget:
                st.error(
                    "This would exceed the allocated budget. Approval cannot "
                    "bypass the budget check — reject, ask for clarification, "
                    "or raise the budget first."
                )

            reason_required = action != "Approve"

            note_label = (
                "Reason (required)"
                if reason_required
                else "Notes (optional)"
            )

            note_text = st.text_area(
                note_label
            )

            can_submit = (
                not approval_blocked
                and (
                    bool(note_text.strip())
                    if reason_required
                    else True
                )
            )

            if st.button(
                "Submit Decision",
                type="primary",
                disabled=not can_submit,
            ):
                try:
                    if action == "Approve":
                        client.approve(
                            invoice["invoice_id"],
                            notes=(
                                note_text.strip()
                                or None
                            ),
                        )

                        flash("Invoice approved successfully.", "success")

                    elif action == "Reject":
                        client.reject(
                            invoice["invoice_id"],
                            reason=note_text,
                        )

                        flash("Invoice rejected.", "success")

                    else:
                        client.clarify(
                            invoice["invoice_id"],
                            reason=note_text,
                        )

                        flash("Clarification requested.", "success")

                    st.rerun()

                except APIError as e:
                    st.error(
                        e.detail
                    )

        else:
            # Terminal or pre-queue status (approved, rejected, submitted,
            # etc.) — no decision can be made here anymore.
            st.info(
                f"This invoice's current status is "
                f"**{invoice['status'].replace('_', ' ').title()}**. "
                "No further review action is available."
            )

        st.caption("Decision support only — this action is final once submitted and is recorded in the audit trail.")