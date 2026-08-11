from sqlalchemy.orm import Session

from app.models.invoice import Invoice

from app.audit.audit_logger import (
    create_audit_log,
)

from app.audit.audit_context import (
    build_status_change_note,
)


def reject_invoice(
    db: Session,
    invoice: Invoice,
    user_id: int,
    reason: str,
):

    if invoice.status != "pending_review":
        raise ValueError(
            "Only invoices pending review "
            "can be rejected."
        )

    if not reason.strip():
        raise ValueError(
            "Rejection reason is required."
        )

    old_status = invoice.status

    invoice.status = "rejected"

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    audit_note = build_status_change_note(
        old_status=old_status,
        new_status="rejected",
        reason=reason,
    )

    create_audit_log(
        db=db,
        action="rejected",
        user_id=user_id,
        invoice_id=invoice.invoice_id,
        notes=audit_note,
    )

    return invoice