import pandas as pd
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
    APIError,
    get_client,
    require_login,
)
from utils.invoice_picker import pick_invoice
from utils.alert_cards import render_alert_cards
from utils.notifications import (
    show_flash_messages,
)


st.set_page_config(
    page_title="Matter & Budget Context | Konverge",
    page_icon="🏛️",
    layout="wide",
)

inject_base_css()
sidebar_brand()
require_login()

show_flash_messages()

client = get_client()

invoice = pick_invoice(
    label="Open Invoice"
)

if not invoice:
    st.stop()


try:
    hierarchy = (
        client.get_budget_hierarchy()
        or []
    )

    alerts = (
        client.list_alerts(
            active_only=True
        )
        or []
    )

except APIError as exc:
    st.error(
        f"Couldn't load matter and budget data: "
        f"{exc.detail}"
    )
    st.stop()


selected_firm = None
selected_matter = None


for firm in hierarchy:

    for matter in firm["matters"]:

        if (
            matter["matter_id"]
            == invoice["matter_id"]
        ):
            selected_firm = firm
            selected_matter = matter
            break

    if selected_matter:
        break


if not selected_matter:
    st.error(
        "No budget context was found for this invoice's matter."
    )
    st.stop()


current_row = next(
    (
        row
        for row in selected_matter["invoices"]
        if row["invoice_id"]
        == invoice["invoice_id"]
    ),
    None,
)


page_header(
    4,
    "Matter & Budget Context",
    (
        "Matter, firm, invoice impact, current budget position, "
        "and actionable alerts in one place."
    ),
    extra_badge=badge(
        (
            "Attention Required"
            if (
                current_row
                and current_row["needs_attention"]
            )
            else "Budget Checked"
        ),
        (
            "orange"
            if (
                current_row
                and current_row["needs_attention"]
            )
            else "green"
        ),
    ),
)


left, right = st.columns([3.1, 1])


# ============================================================================
# ALERTS
# ============================================================================

with right:

    with st.container(border=True):

        st.markdown("#### 🔔 Alerts")

        matter_alerts = [
            alert
            for alert in alerts
            if (
                alert["budget_id"]
                == selected_matter["budget_id"]
            )
        ]

        dismissed = render_alert_cards(
            client,
            matter_alerts,
            key_prefix=(
                f"matter_{selected_matter['budget_id']}"
            ),
            empty_message=(
                "No active alerts for this matter."
            ),
            compact=True,
        )

        if dismissed:
            st.rerun()


# ============================================================================
# FIRM / MATTER / BUDGET
# ============================================================================

with left:

    c1, c2 = st.columns(2)

    with c1:

        with st.container(border=True):

            st.markdown("#### Firm")

            kv_row(
                "Firm Name",
                selected_firm["firm_name"],
            )

            kv_row(
                "Address",
                selected_firm.get(
                    "firm_address"
                )
                or "—",
            )

    with c2:

        with st.container(border=True):

            st.markdown("#### Matter")

            kv_row(
                "Matter ID",
                (
                    selected_matter.get(
                        "matter_no"
                    )
                    or str(
                        selected_matter[
                            "matter_id"
                        ]
                    )
                ),
            )

            kv_row(
                "Matter Name",
                selected_matter[
                    "matter_name"
                ],
            )

    st.markdown("## Budget Decision")

    if current_row:

        d1, d2, d3, d4 = st.columns(4)

        d1.metric(
            "Invoice Amount",
            f"${current_row['amount']:,.2f}",
        )

        d2.metric(
            "Effective Budget",
            f"${selected_matter['allocated']:,.2f}",
        )

        d3.metric(
            "Projected Remaining",
            (
                f"${current_row['remaining_after_invoice']:,.2f}"
            ),
        )

        projected_utilization = (
            current_row.get(
                "projected_utilization"
            )
        )

        if projected_utilization is not None:

            d4.metric(
                "Projected Utilization",
                (
                    f"{float(projected_utilization):.1f}%"
                ),
            )

        else:

            invoice_amount = float(
                current_row.get("amount")
                or 0
            )

            effective_budget = float(
                selected_matter.get(
                    "allocated"
                )
                or 0
            )

            approved_spend = float(
                selected_matter.get(
                    "utilized"
                )
                or 0
            )

            if effective_budget > 0:

                calculated_utilization = (
                    (
                        approved_spend
                        + invoice_amount
                    )
                    / effective_budget
                ) * 100

                d4.metric(
                    "Projected Utilization",
                    (
                        f"{calculated_utilization:.1f}%"
                    ),
                )

            else:

                d4.metric(
                    "Projected Utilization",
                    "—",
                )

        result = current_row[
            "budget_result"
        ]

        if result == "over_budget":

            notice(
                (
                    "OVER BUDGET — this invoice cannot clear "
                    "the budget gate until the budget is adjusted "
                    "or an authorized override is used."
                )
            )

        elif result == "threshold_reached":

            notice(
                (
                    "BUDGET THRESHOLD REACHED — warning only. "
                    "The invoice may still be approved if all "
                    "other validation checks pass."
                )
            )

        else:

            notice(
                (
                    "WITHIN BUDGET — no budget blocker "
                    "is present."
                ),
                success=True,
            )

        if current_row.get(
            "validation_message"
        ):

            st.markdown(
                "#### Why This Invoice Is Pending / What To Resolve"
            )

            for reason in [
                value.strip()
                for value in current_row[
                    "validation_message"
                ].split(";")
                if value.strip()
            ]:

                st.warning(reason)

        if current_row.get(
            "intake_budget_result"
        ):

            st.caption(
                (
                    "Historical intake snapshot: "
                    + current_row[
                        "intake_budget_result"
                    ]
                    .replace("_", " ")
                    .title()
                )
                + (
                    (
                        f" · remaining after intake "
                        f"${current_row['intake_remaining_after_invoice']:,.2f}"
                    )
                    if current_row.get(
                        "intake_remaining_after_invoice"
                    )
                    is not None
                    else ""
                )
            )

    else:

        st.warning(
            "The selected invoice could not be found in the budget hierarchy."
        )


    # ========================================================================
    # RELATED INVOICES
    # ========================================================================

    st.markdown(
        "## Related Invoices for This Matter"
    )

    rows = []

    for row in selected_matter["invoices"]:

        invoice_label = (
            row.get("invoice_no")
            or f"#{row['invoice_id']}"
        )

        if row.get(
            "is_newest_invoice"
        ):
            invoice_label += " 🆕"

        rows.append(
            {
                "Invoice No.": invoice_label,

                "Amount": (
                    f"${row['amount']:,.2f}"
                ),

                "Status": (
                    row["status"]
                    .replace("_", " ")
                    .title()
                ),

                "Budget Result": (
                    row["budget_result"]
                    .replace("_", " ")
                    .title()
                ),

                "Remaining After Invoice": (
                    f"${row['remaining_after_invoice']:,.2f}"
                ),

                "Needs Attention": (
                    "Yes"
                    if row["needs_attention"]
                    else "No"
                ),

                "Current Invoice": (
                    "Yes"
                    if (
                        row["invoice_id"]
                        == invoice["invoice_id"]
                    )
                    else ""
                ),

                "_attention": (
                    row["needs_attention"]
                ),
            }
        )


    if rows:

        df = pd.DataFrame(rows)

        display = df.drop(
            columns=["_attention"]
        )

        def highlight(row):
            attention = rows[
                row.name
            ]["_attention"]

            return [
                (
                    "background-color: #ffe4e6; "
                    "font-weight: 600"
                )
                if attention
                else ""
                for _ in row
            ]

        st.dataframe(
            display.style.apply(
                highlight,
                axis=1,
            ),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.caption(
            "No related invoices were found."
        )


    # ========================================================================
    # BUDGET ACTIVITY
    # ========================================================================

    st.markdown("## Budget Activity")

    try:

        adjustments = (
            client.list_budget_adjustments(
                selected_matter["budget_id"]
            )
            or []
        )

        ledger = (
            client.list_budget_ledger(
                budget_id=selected_matter[
                    "budget_id"
                ]
            )
            or []
        )

    except APIError as exc:

        adjustments = []
        ledger = []

        st.warning(
            f"Couldn't load budget activity: "
            f"{exc.detail}"
        )


    invoice_names = {
        row["invoice_id"]: (
            row.get("invoice_no")
            or f"#{row['invoice_id']}"
        )
        for row in selected_matter[
            "invoices"
        ]
    }


    activity = []


    for item in adjustments:

        activity.append(
            {
                "created_at": item[
                    "created_at"
                ],

                "Activity": (
                    f"Budget "
                    f"{item['adjustment_type'].title()}"
                ),

                "Invoice": (
                    item.get("invoice_no")
                    or "—"
                ),

                "Amount / Change": (
                    f"${item['adjustment_amount']:+,.2f}"
                ),

                "Budget After": (
                    f"${item['new_amount']:,.2f}"
                ),

                "Reason": item["reason"],

                "Confirmed": (
                    "Yes"
                    if item["confirmed"]
                    else "No"
                ),
            }
        )


    for item in ledger:

        activity.append(
            {
                "created_at": item[
                    "created_at"
                ],

                "Activity": (
                    "Invoice Approved"
                ),

                "Invoice": (
                    invoice_names.get(
                        item["invoice_id"],
                        f"#{item['invoice_id']}",
                    )
                ),

                "Amount / Change": (
                    f"${item['amount']:,.2f}"
                ),

                "Budget After": "—",

                "Reason": "—",

                "Confirmed": "—",
            }
        )


    if activity:

        activity.sort(
            key=lambda value: str(
                value["created_at"]
            ),
            reverse=True,
        )

        activity_df = (
            pd.DataFrame(activity)
            .drop(columns=["created_at"])
        )

        st.dataframe(
            activity_df,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.caption(
            "No budget activity recorded yet."
        )


if st.button(
    "Continue to Validation & Duplicate Check →",
    type="primary",
):
    st.switch_page(
        "pages/5_Validation_Check.py"
    )