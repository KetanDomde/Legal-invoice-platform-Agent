from sqlalchemy.orm import Session
from app.models.invoice import Invoice
from app.audit.audit_logger import (
    create_audit_log,
)


def approve_invoice(
    db: Session,
    invoice: Invoice,
    user_id: int,
    notes: str | None = None,
):
    """
    Approve an invoice from the review queue.
    """

    if invoice.status not in [
        "pending_review",
        "clarification_requested",
        "submitted",
    ]:
        raise ValueError(
            f"Invoice cannot be approved "
            f"from status '{invoice.status}'."
        )

    invoice.status = "approved"

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    create_audit_log(
        db=db,
        action="invoice_approved",
        user_id=user_id,
        invoice_id=invoice.invoice_id,
        notes=notes or "Invoice approved.",
    )

    return invoice