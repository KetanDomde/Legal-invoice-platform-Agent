import streamlit as st

from utils.theme import (
    badge,
    inject_base_css,
    kv_row,
    notice,
    page_header,
    sidebar_brand,
)
from utils.api_client import (
    get_client,
    require_login,
    APIError,
)
from utils.invoice_picker import pick_invoice


st.set_page_config(
    page_title="Validation & Duplicate Check | Konverge",
    page_icon="🔍",
    layout="wide",
)

inject_base_css()
sidebar_brand()
require_login()

client = get_client()
user = st.session_state["user"]

invoice = pick_invoice(
    label="Open Invoice"
)

if not invoice:
    st.stop()


overall_ok = (
    invoice.get("budget_valid") is True
    and not invoice.get("duplicate_flag")
)


page_header(
    5,
    "Validation & Duplicate Check",
    (
        "Server-computed extraction confidence, budget validity, "
        "and duplicate detection for this invoice."
    ),
    extra_badge=(
        badge("Checks Passed", "green")
        if overall_ok
        else badge("Needs Attention", "orange")
    ),
)


left, right = st.columns([2, 1])


with left:
    with st.container(border=True):
        st.markdown(
            "#### Detected Checks"
        )

        confidence = invoice.get(
            "confidence_score"
        )

        rows = [
            {
                "Check": "Extraction Confidence",
                "Result": (
                    f"{confidence:.0%}"
                    if confidence is not None
                    else "—"
                ),
                "Status": (
                    "High"
                    if (confidence or 0) >= 0.85
                    else "Low"
                ),
            },
            {
                "Check": "Budget Valid",
                "Result": (
                    "Yes"
                    if invoice.get("budget_valid") is True
                    else (
                        "No"
                        if invoice.get("budget_valid") is False
                        else "Not yet checked"
                    )
                ),
                "Status": (
                    "High"
                    if invoice.get("budget_valid") is True
                    else (
                        "Low"
                        if invoice.get("budget_valid") is False
                        else "Medium"
                    )
                ),
            },
            {
                "Check": "Possible Duplicate",
                "Result": (
                    "Yes"
                    if invoice.get("duplicate_flag")
                    else "No"
                ),
                "Status": (
                    "Low"
                    if invoice.get("duplicate_flag")
                    else "High"
                ),
            },
        ]

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown(
            "#### Validation Message"
        )

        if invoice.get(
            "validation_status"
        ):
            st.markdown(
                f"**Validation status:** "
                f"{invoice['validation_status'].replace('_', ' ').title()}"
            )

        if invoice.get(
            "validation_message"
        ):
            notice(
                invoice["validation_message"],
                success=(
                    invoice.get("validation_status")
                    == "passed"
                ),
            )
        else:
            st.caption(
                "No validation message recorded yet."
            )


with right:
    with st.container(border=True):
        st.markdown(
            "#### Human Review Flags"
        )

        flags = []

        if (
            invoice.get("confidence_score") is not None
            and invoice["confidence_score"] < 0.85
        ):
            flags.append(
                "Low extraction confidence"
            )

        if invoice.get("duplicate_flag"):
            flags.append(
                "Possible duplicate"
            )

        if invoice.get("budget_valid") is False:
            flags.append(
                "Budget conflict or no budget configured"
            )

        if flags:
            st.markdown(
                "".join(
                    (
                        f'<span style="display:inline-block;'
                        f'margin:3px 3px 3px 0">'
                        f'{badge(flag, "orange")}</span>'
                    )
                    for flag in flags
                ),
                unsafe_allow_html=True,
            )
        else:
            st.caption(
                "No flags raised."
            )

        if user["role"] in ("admin", "editor"):
            st.markdown(
                "#### Re-run Validation"
            )

            st.caption(
                "Budget validity is calculated by the server from "
                "the BudgetLedger and cannot be manually overridden here."
            )

            with st.form(
                "manual_validation"
            ):
                duplicate_choice = st.checkbox(
                    "Mark as duplicate",
                    value=bool(
                        invoice.get(
                            "duplicate_flag"
                        )
                    ),
                )

                confidence_override = st.slider(
                    "Confidence override",
                    0.0,
                    1.0,
                    float(
                        invoice.get(
                            "confidence_score"
                        )
                        or 0.5
                    ),
                )

                if st.form_submit_button(
                    "Apply Validation",
                    type="primary",
                ):
                    try:
                        result = client.validate_invoice(
                            invoice["invoice_id"],
                            duplicate_flag=duplicate_choice,
                            confidence_score=confidence_override,
                        )

                        st.success(
                            f"Decision: "
                            f"{result['decision']} — "
                            f"{', '.join(result.get('reasons', []))}"
                        )

                        st.session_state[
                            "selected_invoice_id"
                        ] = invoice["invoice_id"]

                        st.rerun()

                    except APIError as e:
                        st.error(
                            e.detail
                        )


st.markdown("---")

if st.button(
    "Continue to Review Queue →",
    type="primary",
):
    st.switch_page(
        "pages/6_Review_Queue.py"
    )