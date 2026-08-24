from sqlalchemy.orm import Session
from app.models.invoice import Invoice
from app.services.review_service import (
    build_review_reasons,
)


REVIEW_STATUSES = [
    "pending_review",
    "clarification_requested",
]

def get_review_queue(
    db: Session,
    firm_id: int,
):
    """
    Return invoices requiring human review
    for the current firm.
    """

    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.firm_id == firm_id,
            Invoice.status == "pending_review",
        )
        .order_by(
            Invoice.invoice_date.asc()
        )
        .all()
    )
    
    results = []

    for invoice in invoices:

        results.append(
            {
                "invoice_id": invoice.invoice_id,
                "matter_id": invoice.matter_id,
                "firm_id": invoice.firm_id,
                "invoice_no": invoice.invoice_no,
                "invoice_date": invoice.invoice_date,
                "total_amount": invoice.total_amount,
                "status": invoice.status,
                "confidence_score": invoice.confidence_score,
                "budget_valid": invoice.budget_valid,
                "duplicate_flag": invoice.duplicate_flag,
                "validation_status": invoice.validation_status,
                "validation_message": invoice.validation_message,
                "review_reasons": build_review_reasons(
                    invoice
                ),
            }
        )

    return results