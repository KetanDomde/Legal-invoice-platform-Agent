from sqlalchemy.orm import Session

from app.models.invoice import Invoice

from app.audit.audit_logger import (
    create_audit_log,
)

from app.audit.audit_context import (
    build_status_change_note,
)

from app.integrations.budget_service import (
    post_approved_invoice_to_budget,
)


def approve_invoice(
    db: Session,
    invoice: Invoice,
    user_id: int,
    notes: str | None = None,
):
    """
    Approve an invoice after human review.
    """

    if invoice.status != "pending_review":
        raise ValueError(
            "Only invoices pending review "
            "can be approved."
        )

    # --------------------------------------------------
    # Budget integration
    # --------------------------------------------------

    budget_result = (
        post_approved_invoice_to_budget(
            db=db,
            invoice=invoice,
        )
    )

    # --------------------------------------------------
    # Update invoice
    # --------------------------------------------------
    old_status = invoice.status
    invoice.status = "approved"

    db.add(invoice)

    db.commit()

    db.refresh(invoice)

    # --------------------------------------------------
    # Audit
    # --------------------------------------------------

    # audit_notes = (
    #     f"Invoice approved. "
    #     f"Budget posted: "
    #     f"{budget_result['amount_posted']}."
    # )

    # if notes:
    #     audit_notes += f" Notes: {notes}"
    
    
    audit_note = build_status_change_note(
    old_status=old_status,
    new_status="approved",
    reason=notes,
    )
    
    create_audit_log(
        db=db,
        action="approved",
        user_id=user_id,
        invoice_id=invoice.invoice_id,
        notes=audit_note,
    )

    return invoice