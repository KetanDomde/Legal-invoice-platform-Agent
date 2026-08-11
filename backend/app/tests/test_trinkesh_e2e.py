from datetime import date
from decimal import Decimal

from app.models.user import User
from app.models.invoice import Invoice
from app.models.audit_log import AuditLog


def test_trinkesh_review_flow(client, db):
    # -----------------------------------------
    # 1. Create Editor
    # -----------------------------------------

    user = User(
        name="Trinkesh Test Editor",
        email="trinkesh-e2e@test.com",
        password_hash="test-password-hash",
        role="editor",
        firm_id=1,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # -----------------------------------------
    # 2. Create test invoice
    # -----------------------------------------

    invoice = Invoice(
        firm_id=1,
        matter_id=1,
        invoice_no="E2E-TRINKESH-001",
        invoice_date=date(2026, 1, 15),
        total_amount=Decimal("1500.00"),
        confidence_score=0.60,
        status="processing",
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    # -----------------------------------------
    # 3. Get JWT
    # -----------------------------------------
    #
    # IMPORTANT:
    # Use the same token helper that your
    # existing review API tests use.
    #

    token = create_test_token(user)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # -----------------------------------------
    # 4. Validate invoice
    # -----------------------------------------

    response = client.post(
        f"/validation/{invoice.invoice_id}",
        headers=headers,
        params={
            "budget_valid": True,
            "duplicate_flag": False,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["decision"] == "pending_review"
    assert data["status"] == "pending_review"

    # -----------------------------------------
    # 5. Check review queue
    # -----------------------------------------

    response = client.get(
        "/review/queue",
        headers=headers,
    )

    assert response.status_code == 200

    queue = response.json()

    queued_invoice = next(
        item
        for item in queue
        if item["invoice_id"]
        == invoice.invoice_id
    )

    assert (
        queued_invoice["status"]
        == "pending_review"
    )

    # -----------------------------------------
    # 6. Approve
    # -----------------------------------------

    response = client.post(
        f"/review/{invoice.invoice_id}/approve",
        headers=headers,
    )

    assert response.status_code == 200

    # -----------------------------------------
    # 7. Verify invoice status
    # -----------------------------------------

    db.refresh(invoice)

    assert invoice.status == "approved"

    # -----------------------------------------
    # 8. Verify audit
    # -----------------------------------------

    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.invoice_id
            == invoice.invoice_id,

            AuditLog.action
            == "approved",
        )
        .first()
    )

    assert audit is not None

    assert audit.user_id == user.user_id

    assert (
        audit.invoice_id
        == invoice.invoice_id
    )