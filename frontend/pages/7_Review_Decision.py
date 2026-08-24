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
require_role("admin", "editor")

client = get_client()

invoice = pick_invoice(
    label="Invoice to Decide"
)

if not invoice:
    st.stop()


try:
    review_inv = client.get_review_invoice(
        invoice["invoice_id"]
    )
except APIError as e:
    review_inv = None
    st.warning(
        (
            "Couldn't load review-queue context "
            f"(it may already be decided): {e.detail}"
        )
    )


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


page_header(
    7,
    "Review & Decision",
    (
        "Full context for one invoice, and the decision "
        "that moves it out of the queue."
    ),
    extra_badge=status_badge(
        invoice["status"]
    ),
)


left, right = st.columns([2, 1])


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

        kv_row(
            "Possible Duplicate",
            (
                "Yes"
                if invoice.get("duplicate_flag")
                else "No"
            ),
        )

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

        elif invoice["status"] not in (
            "under_review",
            "pending_review",
            "clarification_requested",
        ):
            notice(
                (
                    f"This invoice's current status is "
                    f"**{invoice['status'].replace('_', ' ').title()}** "
                    "— it may already be decided."
                )
            )


with right:
    with st.container(border=True):
        st.markdown(
            "#### Decision"
        )

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

        if (
            action == "Approve"
            and no_budget
        ):
            st.error(
                "This matter has no configured budget. "
                "Approval is blocked until a budget is created."
            )

        if (
            action == "Approve"
            and over_budget
            and not no_budget
        ):
            st.warning(
                (
                    "This approval will exceed the allocated budget. "
                    "You may override the budget, but a reason is mandatory."
                )
            )

        reason_required = (
            action != "Approve"
            or (
                action == "Approve"
                and over_budget
                and not no_budget
            )
        )

        note_label = (
            "Reason (required)"
            if reason_required
            else "Notes (optional)"
        )

        note_text = st.text_area(
            note_label
        )

        can_submit = (
            not (
                action == "Approve"
                and no_budget
            )
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

                    if over_budget:
                        flash("Invoice approved as a documented budget override.", "success")
                    else:
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

        st.caption(
            (
                "All decisions are recorded in the audit trail. "
                "Budget overrides require a documented reason."
            )
        )


st.markdown("---")

if st.button(
    "← Back to Review Queue"
):
    st.switch_page(
        "pages/6_Review_Queue.py"
    )