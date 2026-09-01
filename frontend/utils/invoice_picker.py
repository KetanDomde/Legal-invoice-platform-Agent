"""
Shared "which invoice am I looking at" selector used by every per-invoice
workbench screen (Workspace, Matter & Budget Context, Validation Check,
Review Decision) — keeps the choice in st.session_state so opening an
invoice from the Inbox or the Review Queue carries it through the whole
flow, but still lets you switch invoices from any of those screens.
"""
import streamlit as st

from utils.api_client import APIError, get_client

def pick_invoice(
    label: str = "Invoice",
    matter_id: int | None = None,
    firm_id: int | None = None,
):
    """
    Renders a selectbox of invoices.

    Optional matter_id and firm_id filters are passed directly to the
    backend invoice endpoint.

    Returns the selected InvoiceRead dict.
    """

    client = get_client()

    try:
        invoices = client.list_invoices(
            matter_id=matter_id,
            firm_id=firm_id,
        )
    except APIError as e:
        st.error(f"Couldn't load invoices: {e.detail}")
        return None

    if not invoices:
        st.info("No invoices found for the selected filters.")
        return None

    invoices = sorted(
        invoices,
        key=lambda i: i["invoice_id"],
        reverse=True,
    )

    def _label(inv):
        display_no = (
            inv.get("invoice_no")
            or f"Invoice #{inv['invoice_id']}"
        )

        return f"{display_no}  ·  #{inv['invoice_id']}"

    labels = [_label(i) for i in invoices]

    selected_id = st.session_state.get("selected_invoice_id")

    default_index = 0

    for idx, invoice in enumerate(invoices):
        if invoice["invoice_id"] == selected_id:
            default_index = idx
            break

    chosen_label = st.selectbox(
        label,
        labels,
        index=default_index,
    )

    chosen = invoices[labels.index(chosen_label)]

    st.session_state["selected_invoice_id"] = chosen["invoice_id"]

    return chosen