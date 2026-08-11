from decimal import Decimal

def post_approved_invoice_to_budget(
    db,
    invoice,
):
    """
    Adapter between Trinkesh's approval workflow
    and the budget module.

    Replace the internal implementation with
    Rajat's budget service when that module is
    merged.
    """

    amount = invoice.total_amount

    if amount is None:
        raise ValueError(
            "Invoice amount is required before approval."
        )

    if amount <= Decimal("0"):
        raise ValueError(
            "Invoice amount must be greater than zero."
        )

    # --------------------------------------------------
    # TODO:
    # Replace this section with Rajat's actual
    # budget ledger service.
    # --------------------------------------------------

    return {
        "invoice_id": invoice.invoice_id,
        "amount_posted": amount,
        "status": "posted",
    }