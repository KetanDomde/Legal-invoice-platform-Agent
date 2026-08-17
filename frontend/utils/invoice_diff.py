"""
Shared renderer for duplicate-invoice diff payloads (the `inv_changes`
dict produced by diff_invoices() in backend/app/services/invoice.py and
returned in the 409 body of POST /invoices/submit). Used by both Home.py
and pages/2_Invoices.py so the duplicate-submission UI stays in one place.
"""
import pandas as pd
import streamlit as st

from utils.theme import GREEN, ORANGE, RED, money

_MONEY_FIELDS = {"amount", "rate", "total_amount"}


def _fmt(field: str, value):
    if value is None:
        return "—"
    if field in _MONEY_FIELDS:
        return money(value)
    return str(value)


def _diff_table(changes: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Field": field.replace("_", " ").title(),
                "Existing invoice": _fmt(field, change["original"]),
                "New submission": _fmt(field, change["duplicate"]),
            }
            for field, change in changes.items()
        ]
    )


def _line_item_summary(item: dict) -> str:
    return (
        f'{item.get("timekeeper") or "—"}, '
        f'{item.get("hours") or 0} hrs @ {money(item.get("rate"))} = {money(item.get("amount"))}'
    )


def render_invoice_diff(inv_changes: dict | None):
    """Renders a diff_invoices() payload as readable tables/cards.

    Shows a friendly "no differences" message when inv_changes is empty
    (e.g. an identical resubmission) rather than silently rendering
    nothing.
    """
    if not inv_changes:
        st.caption("No field differences from the existing invoice — it's an identical resubmission.")
        return

    line_item_diffs = inv_changes.get("line_items") or []
    scalar_changes = {k: v for k, v in inv_changes.items() if k != "line_items"}

    if scalar_changes:
        st.write("**Invoice-level changes**")
        st.dataframe(_diff_table(scalar_changes), hide_index=True, use_container_width=True)

    for entry in line_item_diffs:
        index = entry.get("index", 0)
        status = entry.get("status")

        if status == "added":
            st.markdown(
                f'<div style="border-left:4px solid {GREEN};padding:8px 12px;margin-bottom:6px;'
                f'background:#F4FBF8;border-radius:6px;">'
                f'<b>Line {index + 1} added</b> — {_line_item_summary(entry["duplicate"])}</div>',
                unsafe_allow_html=True,
            )
        elif status == "removed":
            st.markdown(
                f'<div style="border-left:4px solid {RED};padding:8px 12px;margin-bottom:6px;'
                f'background:#FBF4F4;border-radius:6px;">'
                f'<b>Line {index + 1} removed</b> — {_line_item_summary(entry["original"])}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="border-left:4px solid {ORANGE};padding-left:12px;margin-bottom:4px;">'
                f'<b>Line {index + 1} modified</b></div>',
                unsafe_allow_html=True,
            )
            st.dataframe(_diff_table(entry.get("changes", {})), hide_index=True, use_container_width=True)
