"""
Shared "which invoice am I looking at" selector used by every per-invoice
workbench screen (Workspace, Matter & Budget Context, Validation Check,
Review Decision) — keeps the choice in st.session_state so opening an
invoice from the Inbox or the Review Queue carries it through the whole
flow, but still lets you switch invoices from any of those screens.
"""
import streamlit as st

from utils.api_client import APIError, get_client


def pick_invoice(label: str = "Invoice"):
    """
    Renders a selectbox of invoices, defaulting to
    st.session_state["selected_invoice_id"] if set, and returns the full
    InvoiceRead dict for whichever one is chosen (or None if there are no
    invoices yet, or the API call failed — an error is already shown).
    """
    client = get_client()
    try:
        invoices = client.list_invoices()
    except APIError as e:
        st.error(f"Couldn't load invoices: {e.detail}")
        return None

    if not invoices:
        st.info("No invoices yet — submit one from **New Intake** first.")
        return None

    invoices = sorted(invoices, key=lambda i: i["invoice_id"], reverse=True)

    def _label(inv):
        display_no = inv.get("invoice_no") or f"Invoice #{inv['invoice_id']}"
        return f"{display_no}  ·  #{inv['invoice_id']}"

    labels = [_label(i) for i in invoices]
    selected_id = st.session_state.get("selected_invoice_id")
    default_index = 0
    for idx, i in enumerate(invoices):
        if i["invoice_id"] == selected_id:
            default_index = idx
            break

    chosen_label = st.selectbox(label, labels, index=default_index)
    chosen = invoices[labels.index(chosen_label)]
    st.session_state["selected_invoice_id"] = chosen["invoice_id"]
    return chosen
