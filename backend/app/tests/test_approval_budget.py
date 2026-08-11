from decimal import Decimal
from datetime import date
from app.models.invoice import Invoice
from app.workflow.approval_service import (
    approve_invoice,
)
from app.models.audit_log import AuditLog

def test_approval_posts_budget(
    db,
    monkeypatch,
):

    invoice = Invoice(
        firm_id=1,
        matter_id=1,
        invoice_no="APPROVE-001",
        status="pending_review",
        invoice_date=date(2026, 8, 1),

        total_amount=Decimal("1500.00"),
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    captured = {}

    def fake_budget_post(
        db,
        invoice,
    ):
        captured["invoice_id"] = (
            invoice.invoice_id
        )

        captured["amount"] = (
            invoice.total_amount
        )

        return {
            "invoice_id": invoice.invoice_id,
            "amount_posted": invoice.total_amount,
            "status": "posted",
        }

    monkeypatch.setattr(
        "app.workflow.approval_service."
        "post_approved_invoice_to_budget",
        fake_budget_post,
    )

    result = approve_invoice(
        db=db,
        invoice=invoice,
        user_id=100,
        notes="Approved after review",
    )

    assert result.status == "approved"
    
    audit = (
    db.query(AuditLog)
    .filter(
        AuditLog.invoice_id == invoice.invoice_id,
        AuditLog.action == "approved",
    )
    .first()
)

    assert audit is not None
    assert audit.user_id == 100
    assert audit.invoice_id == invoice.invoice_id
    assert audit.action == "approved"

    assert "pending_review" in audit.notes
    assert "approved" in audit.notes

    assert (
        captured["invoice_id"]
        == invoice.invoice_id
    )

    assert (
        captured["amount"]
        == Decimal("1500.00")
    )
    
    

def test_only_pending_review_can_be_approved(
    db,
):

    invoice = Invoice(
        firm_id=1,
        matter_id=1,
        invoice_no="APPROVE-002",
        status="approved",
        invoice_date=date(2026, 8, 1),

        total_amount=Decimal("1000.00"),
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    try:

        approve_invoice(
            db=db,
            invoice=invoice,
            user_id=100,
        )

        assert False, (
            "Approval should have failed"
        )

    except ValueError as exc:

        assert (
            "pending review"
            in str(exc).lower()
        )