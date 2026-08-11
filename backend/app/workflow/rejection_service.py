from sqlalchemy.orm import Session

from app.models.invoice import Invoice

from app.audit.audit_logger import (
    create_audit_log,
)


def reject_invoice(
    db: Session,
    invoice: Invoice,
    user_id: int,
    reason: str,
):
    """
    Reject an invoice.

    A rejection reason is mandatory.
    """

    if not reason or not reason.strip():
        raise ValueError(
            "Rejection reason is required."
        )

    if invoice.status not in [
        "pending_review",
        "clarification_requested",
        "submitted",
    ]:
        raise ValueError(
            f"Invoice cannot be rejected "
            f"from status '{invoice.status}'."
        )

    invoice.status = "rejected"

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    create_audit_log(
        db=db,
        action="invoice_rejected",
        user_id=user_id,
        invoice_id=invoice.invoice_id,
        notes=reason.strip(),
    )

    return invoice