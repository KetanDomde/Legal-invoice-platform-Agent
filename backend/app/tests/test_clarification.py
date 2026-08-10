import pytest

from app.workflow.clarification_service import (
    request_clarification,
)


def test_clarification_requires_note():

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
        match="Clarification note is required",
    ):

        request_clarification(
            db=None,
            invoice=invoice,
            user_id=1,
            note="",
        )