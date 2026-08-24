from __future__ import annotations

import streamlit as st

from utils.api_client import APIError


def _alert_icon(alert: dict) -> str:
    alert_type = str(alert.get("type") or "").lower()

    if "over" in alert_type or "overrun" in alert_type:
        return "🔴"

    if "threshold" in alert_type:
        return "⚠️"

    return "ℹ️"


def _alert_title(alert: dict) -> str:
    alert_type = str(alert.get("type") or "").lower()

    if "over" in alert_type or "overrun" in alert_type:
        return "Over Budget"

    if "threshold" in alert_type:
        return "Budget Threshold Reached"

    return str(alert.get("type") or "Budget Alert").replace("_", " ").title()


def render_alert_cards(
    client,
    alerts: list[dict],
    *,
    key_prefix: str,
    empty_message: str = "No active alerts.",
    compact: bool = False,
) -> bool:
    """
    Render active alerts as individual cards.

    Returns True when an alert was dismissed so the caller can rerun the page.
    """

    if not alerts:
        st.success(empty_message)
        return False

    for alert in alerts:
        alert_id = alert.get("alert_id")

        with st.container(border=True):
            title_col, close_col = st.columns([12, 1])

            with title_col:
                st.markdown(
                    f"### {_alert_icon(alert)} {_alert_title(alert)}"
                    if not compact
                    else f"**{_alert_icon(alert)} {_alert_title(alert)}**"
                )

            with close_col:
                if st.button(
                    "✕",
                    key=f"{key_prefix}_dismiss_{alert_id}",
                    help="Dismiss this alert",
                    use_container_width=True,
                ):
                    try:
                        client.dismiss_alert(alert_id)

                        st.session_state["_flash_notifications"] = (
                            st.session_state.get("_flash_notifications", [])
                        )

                        st.session_state["_flash_notifications"].append(
                            {
                                "message": "Alert dismissed successfully.",
                                "level": "success",
                            }
                        )

                        return True

                    except APIError as exc:
                        st.error(f"Couldn't dismiss alert: {exc.detail}")

            firm_name = alert.get("firm_name")
            matter_no = alert.get("matter_no")
            matter_name = alert.get("matter_name")
            invoice_no = alert.get("invoice_no")

            if firm_name:
                st.caption(f"🏢 Firm: {firm_name}")

            if matter_name or matter_no:
                matter_label = " — ".join(
                    [
                        value
                        for value in [
                            matter_no,
                            matter_name,
                        ]
                        if value
                    ]
                )
                st.caption(f"📁 Matter: {matter_label}")

            if invoice_no:
                st.caption(f"📄 Invoice: {invoice_no}")

            st.write(alert.get("message") or "Budget attention required.")

            details = []

            if alert.get("utilization_pct") is not None:
                details.append(
                    f"Utilization: {float(alert['utilization_pct']):.1f}%"
                )

            if alert.get("threshold_pct") is not None:
                details.append(
                    f"Threshold: {float(alert['threshold_pct']):.1f}%"
                )

            if details:
                st.caption(" · ".join(details))

    return False