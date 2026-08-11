from sqlalchemy.orm import Session
from app.models.invoice import Invoice

def update_invoice_status_from_validation(
    db: Session,
    invoice_id: int,
    decision: str,
):
    
    """
    Update invoice status after validation.
    """
    
    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.invoice_id == invoice_id
        )
        .first()
    )

    if invoice is None:
        raise ValueError(
            "Invoice not found."
        )

    if decision == "auto_approve":
        invoice.status = "approved"
    elif decision == "human_review":

        invoice.status = "pending_review"

    else:

        raise ValueError(
            f"Unknown decision: {decision}"
        )

    db.commit()
    db.refresh(invoice)

    return invoice