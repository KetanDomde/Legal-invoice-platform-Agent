import pytest

from app.workflow.rejection_service import (
    reject_invoice,
)


def test_rejection_requires_reason():

    invoice = type(
        "Invoice",
        (),
        {
            "status": "pending_review",
            "invoice_id": 1,
        },
    )()

    with pytest.raises(
        ValueError,
        match="Rejection reason is required",
    ):

        reject_invoice(
            db=None,
            invoice=invoice,
            user_id=1,
            reason="",
        )