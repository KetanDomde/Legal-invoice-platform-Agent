import pytest
from datetime import date
from app.workflow.clarification_service import (
    request_clarification,
)
from app.models.invoice import Invoice
from decimal import Decimal



# def test_clarification_requires_note():

#     invoice = type(
#         "Invoice",
#         (),
#         {
#             "status": "pending_review",
#             "invoice_id": 1,
#         },
#     )()

#     with pytest.raises(
#         ValueError,
#         match="Clarification note is required",
#     ):

#         request_clarification(
#             db=None,
#             invoice=invoice,
#             user_id=1,
#             note="",
#         )
        
def test_request_clarification(
    db,
):

    invoice = Invoice(
        firm_id=1,
        matter_id=1,
        invoice_no="CLARIFY-001",
        status="pending_review",
        invoice_date=date(2026, 8, 1),

        total_amount=Decimal("800.00"),
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    result = request_clarification(
        db=db,
        invoice=invoice,
        user_id=100,
        reason="Missing supporting document.",
    )

    assert (
        result.status
        == "clarification_requested"
    )