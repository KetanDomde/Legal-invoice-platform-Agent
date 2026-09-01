import streamlit as st

from utils.theme import inject_base_css, kv_row, notice, page_header, sidebar_brand
from utils.api_client import get_client, require_login, APIError
from utils.invoice_diff import render_invoice_diff
from utils.notifications import flash, show_flash_messages


st.set_page_config(
    page_title="New Intake | Konverge",
    page_icon="📝",
    layout="wide",
)

inject_base_css()
sidebar_brand()
require_login()

# IMPORTANT:
# Consume notifications on the page where they were created.
# This prevents New Intake messages from appearing later on
# Budgets & Alerts or any other page.
show_flash_messages()


page_header(
    2,
    "New Intake & Extraction",
    "Submit an invoice PDF to the real extraction/validation pipeline and see exactly what came back — "
    "extracted fields, confidence, duplicate check, and classified charges.",
)

client = get_client()
user = st.session_state["user"]


if user["role"] not in ("admin", "editor"):
    st.info("Viewer role: read-only. Ask an Editor or Admin to submit a new invoice.")
    st.stop()


st.caption(
    "The matter and firm are resolved automatically from the invoice text itself (its matter number / matter "
    "name) — a new matter is auto-created if it's the first invoice seen for it. Only fill in the overrides "
    "below if extraction can't find a matter identifier, or you want a newly-created matter routed to a "
    "specific firm."
)


with st.container(border=True):
    st.markdown("#### Submit an Invoice")

    uploaded_file = st.file_uploader(
        "Invoice file (PDF or TXT) *",
        type=["pdf", "txt"],
    )

    with st.expander("Advanced overrides (optional)"):
        c1, c2 = st.columns(2)

        with c1:
            matter_no_override = st.text_input(
                "Matter No. override",
                placeholder="e.g. MAT-771B",
                help=(
                    "Only needed if the invoice has no extractable matter identifier, "
                    "or to force a specific one."
                ),
            )

        with c2:
            firm_name_override = st.text_input(
                "Firm name override",
                placeholder="e.g. Sample Outside Counsel LLP",
                help=(
                    "Used to find-or-create the firm when this submission creates "
                    "a brand-new matter."
                ),
            )

    can_submit = uploaded_file is not None

    if st.button(
        "Submit Intake",
        type="primary",
        disabled=not can_submit,
    ):
        with st.spinner("Extracting, validating, and persisting..."):
            try:
                result = client.submit_invoice(
                    uploaded_file,
                    matter_no=matter_no_override or None,
                    firm_name=firm_name_override or None,
                )

                st.session_state.pop("_last_intake_error", None)

            except APIError as e:
                result = None

                st.session_state.pop("_last_intake_result", None)

                if e.status_code == 409:
                    st.session_state["_last_intake_error"] = {
                        "label": "Duplicate invoice",
                        "detail": e.detail,
                        "inv_changes": getattr(e, "inv_changes", None),
                    }

                elif e.status_code == 422:
                    st.session_state["_last_intake_error"] = {
                        "label": "Couldn't resolve a matter",
                        "detail": (
                            f"{e.detail} Fill in **Matter No. override** above and resubmit."
                        ),
                        "inv_changes": None,
                    }

                else:
                    st.session_state["_last_intake_error"] = {
                        "label": f"API error {e.status_code}",
                        "detail": e.detail,
                        "inv_changes": None,
                    }

        if result is not None:
            # Preserve the result for the next run.
            st.session_state["_last_intake_result"] = result

            # Select this invoice for the rest of the workflow.
            st.session_state["selected_invoice_id"] = result["invoice_id"]

            st.session_state.pop("_last_intake_error", None)

            final_status = (
                result.get("final_status") or ""
            ).replace("_", " ")

            # Queue the messages BEFORE rerunning.
            # The rerun returns to THIS page, where show_flash_messages()
            # at the top consumes them immediately.
            flash(
                (
                    "Invoice uploaded successfully. "
                    f"Current status: {final_status or 'processing complete'}."
                ),
                "success",
            )

            if result.get("final_status") == "approved":
                flash(
                    "Invoice was auto-approved after passing validation.",
                    "success",
                )

            elif result.get("validation_reason"):
                flash(
                    result["validation_reason"],
                    "warning",
                )

        # This rerun is intentional.
        # It lets the result and queued notifications render cleanly.
        st.rerun()


# -------------------------------------------------------------------------
# Intake error
# -------------------------------------------------------------------------

error = st.session_state.pop("_last_intake_error", None)

if error:
    with st.container(border=True):
        st.error(f"🚫 {error['label']}: {error['detail']}")

        if error.get("inv_changes") is not None:
            st.markdown(
                "###### What's different from the invoice already on file"
            )
            render_invoice_diff(error["inv_changes"])


# -------------------------------------------------------------------------
# Successful intake result
# -------------------------------------------------------------------------

result = st.session_state.pop("_last_intake_result", None)

if result:
    extracted = result.get("extracted") or {}

    left, right = st.columns([2, 1])

    with left:
        with st.container(border=True):
            st.markdown("#### Intake Result")

            kv_row(
                "Invoice ID",
                f"#{result['invoice_id']}",
            )

            kv_row(
                "Status",
                (
                    result.get("final_status") or "—"
                ).replace("_", " ").title(),
            )

            kv_row(
                "Invoice No.",
                extracted.get("invoice_no", "—"),
            )

            kv_row(
                "Invoice Date",
                extracted.get("invoice_date") or "—",
            )

            billing_start = extracted.get("billing_period_start")
            billing_end = extracted.get("billing_period_end")

            if billing_start or billing_end:
                kv_row(
                    "Billing Period",
                    f"{billing_start or '—'} to {billing_end or '—'}",
                )

            if (
                extracted.get("matter_no")
                or extracted.get("matter_name")
            ):
                kv_row(
                    "Matter (extracted)",
                    " · ".join(
                        filter(
                            None,
                            [
                                extracted.get("matter_no"),
                                extracted.get("matter_name"),
                            ],
                        )
                    ),
                )

            kv_row(
                "Total Amount",
                (
                    f"${extracted['total_amount']:,.2f}"
                    if extracted.get("total_amount") is not None
                    else "—"
                ),
            )

            line_items = extracted.get("line_items") or []

            def _amount(item):
                try:
                    return float(item.get("amount") or 0)
                except (TypeError, ValueError):
                    return 0.0

            def _line_type(item):
                # Keep legacy rows safe: rows without a timekeeper/hours/rate are
                # expenses even when an older database defaulted line_type to fee.
                value = str(item.get("line_type") or "").strip().lower()
                has_timekeeper = bool(str(item.get("timekeeper") or "").strip())
                has_hours = item.get("hours") is not None
                has_rate = item.get("rate") is not None
                if value == "expense":
                    return "expense"
                if not has_timekeeper and not has_hours and not has_rate:
                    return "expense"
                return "fee"

            fee_items = [item for item in line_items if _line_type(item) == "fee"]
            expense_items = [item for item in line_items if _line_type(item) == "expense"]
            professional_fees = sum(_amount(item) for item in fee_items)
            expenses_total = sum(_amount(item) for item in expense_items)
            classified_total = professional_fees + expenses_total

            st.markdown("#### Invoice Charges")
            st.markdown("##### 👨‍⚖️ Timekeeper Charges")
            if fee_items:
                st.dataframe(
                    [
                        {
                            "Timekeeper": item.get("timekeeper") or "—",
                            "Role": item.get("role") or "—",
                            "Hours": item.get("hours") if item.get("hours") is not None else "—",
                            "Rate": f"${float(item['rate']):,.2f}" if item.get("rate") is not None else "—",
                            "Amount": f"${_amount(item):,.2f}",
                        }
                        for item in fee_items
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption("No timekeeper charges extracted.")
            st.caption(f"Professional fees subtotal: ${professional_fees:,.2f}")

            st.markdown("##### 📎 Expenses")
            if expense_items:
                st.dataframe(
                    [
                        {
                            "Description": item.get("description") or "Expense",
                            "Amount": f"${_amount(item):,.2f}",
                        }
                        for item in expense_items
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption("No expenses extracted.")
            st.caption(f"Expenses subtotal: ${expenses_total:,.2f}")
            st.markdown(f"**Classified charges total: ${classified_total:,.2f}**")

    with right:
        with st.container(border=True):
            st.markdown("#### Validation Check")

            conf = result.get("confidence_score")

            st.metric(
                "Extraction confidence",
                f"{conf:.0%}" if conf is not None else "—",
            )

            if result.get("is_duplicate"):
                notice(
                    "⚠️ Flagged as a duplicate — "
                    f"{result.get('warning', 'routed to human review instead of auto-approve.')}"
                )

            elif result.get("validation_passed") is False:
                notice(
                    "Validation flagged: "
                    f"{result.get('validation_reason') or 'see review queue for details.'}"
                )

            else:
                notice(
                    "All checks passed so far — see the Review Queue if this "
                    "needs a human decision.",
                    success=True,
                )

    if st.button(
        "Open in Invoice Workspace →",
        type="primary",
    ):
        st.switch_page("pages/3_Invoice_Workspace.py")