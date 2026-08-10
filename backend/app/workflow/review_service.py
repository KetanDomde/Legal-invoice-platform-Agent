from sqlalchemy.orm import Session

from app.models.invoice import Invoice


def get_invoice_for_review(
    db: Session,
    invoice_id: int,
    firm_id: int | None = None,
):
    """
    Get one invoice that is available for review.
    """

    query = (
        db.query(Invoice)
        .filter(
            Invoice.invoice_id == invoice_id
        )
    )

    if firm_id is not None:
        query = query.filter(
            Invoice.firm_id == firm_id
        )

    invoice = query.first()

    if invoice is None:
        raise ValueError(
            "Invoice not found."
        )

    return invoice