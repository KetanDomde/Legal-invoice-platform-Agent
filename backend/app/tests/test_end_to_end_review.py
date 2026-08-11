from datetime import date

def test_invoice_review_flow(
    client,
    db,
):

    from app.models.user import User
    from app.models.invoice import Invoice

    from app.auth.password import (
        hash_password,
    )

    from app.auth.jwt_handler import (
        create_access_token,
    )

    # --------------------------------------------------
    # Create Editor
    # --------------------------------------------------

    editor = User(
        name="Editor",
        email="e2e-editor@test.com",
        password_hash=hash_password(
            "Password123!"
        ),
        role="editor",
        firm_id=1,
        is_active=True,
    )

    db.add(editor)
    db.commit()
    db.refresh(editor)

    token = create_access_token(
        {
            "user_id": editor.user_id,
            "role": editor.role,
        }
    )

    # --------------------------------------------------
    # Create invoice
    # --------------------------------------------------

    invoice = Invoice(
        firm_id=1,
        matter_id=1,
        invoice_no="E2E-001",
        invoice_date=date(2026, 8, 1),
        total_amount=5000.00,
        status="processing",
        confidence_score=0.50,
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    validation_response = client.post(
        f"/validation/{invoice.invoice_id}",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
        params={
            "budget_valid": True,
            "duplicate_flag": False,
        },
    )

    assert validation_response.status_code == 200

    assert (
        validation_response.json()["status"]
        == "pending_review"
    )

    # --------------------------------------------------
    # Review queue
    # --------------------------------------------------

    queue_response = client.get(
        "/review/queue",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
    )

    assert queue_response.status_code == 200

    queue = queue_response.json()

    assert any(
        item["invoice_id"]
        == invoice.invoice_id
        for item in queue)