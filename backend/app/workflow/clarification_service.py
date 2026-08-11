from sqlalchemy.orm import Session
from app.models.invoice import Invoice
from app.audit.audit_logger import (
    create_audit_log,
)

def request_clarification(
    db: Session,
    invoice: Invoice,
    user_id: int,
    note: str,
):

    """
    Request clarification from the invoice submitter.
    """

    if not note or not note.strip():
        raise ValueError(
            "Clarification note is required."
        )

    if invoice.status not in [
        "pending_review",
        "submitted",
    ]:
        raise ValueError(
            f"Clarification cannot be requested "
            f"from status '{invoice.status}'."
        )

    invoice.status = "clarification_requested"

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    create_audit_log(
        db=db,
        action="clarification_requested",
        user_id=user_id,
        invoice_id=invoice.invoice_id,
        notes=note.strip(),
    )

    return invoice