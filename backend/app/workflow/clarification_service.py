from sqlalchemy.orm import Session

from app.models.invoice import Invoice

from app.audit.audit_logger import (
    create_audit_log,
)

from app.audit.audit_context import (
    build_status_change_note,
)


def request_clarification(
    db: Session,
    invoice: Invoice,
    user_id: int,
    reason: str,
):

    if invoice.status != "pending_review":
        raise ValueError(
            "Clarification can only be requested "
            "for invoices pending review."
        )

    if not reason.strip():
        raise ValueError(
            "Clarification reason is required."
        )

    old_status = invoice.status

    invoice.status = "clarification_requested"

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    audit_note = build_status_change_note(
        old_status=old_status,
        new_status="clarification_requested",
        reason=reason,
    )

    create_audit_log(
        db=db,
        action="clarification_requested",
        user_id=user_id,
        invoice_id=invoice.invoice_id,
        notes=audit_note,
    )

    return invoice