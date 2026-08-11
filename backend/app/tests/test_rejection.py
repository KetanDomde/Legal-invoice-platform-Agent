from decimal import Decimal
from datetime import date
from app.models.invoice import Invoice

from app.workflow.rejection_service import (
    reject_invoice,
)


def test_reject_invoice(
    db,
):

    invoice = Invoice(
        firm_id=1,
        matter_id=1,
        invoice_no="REJECT-001",
        status="pending_review",
        invoice_date=date(2026, 8, 1),

        total_amount=Decimal("500.00"),
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    result = reject_invoice(
        db=db,
        invoice=invoice,
        user_id=100,
        reason="Duplicate invoice.",
    )

    assert result.status == "rejected"