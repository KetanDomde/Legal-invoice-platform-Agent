from datetime import date
from app.models.user import User
from app.models.invoice import Invoice
from app.auth.password import hash_password
from app.auth.jwt_handler import create_access_token

def create_user(
    db,
    email,
    role="editor",
    firm_id=1,
):
    user = User(
        name="Test User",
        email=email,
        password_hash=hash_password(
            "Password123!"
        ),
        role=role,
        firm_id=firm_id,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_token(user):
    return create_access_token(
        {
            "user_id": user.user_id,
            "role": user.role,
        }
    )

def test_valid_invoice_auto_approves(
    client,
    db,
):
    user = create_user(
        db,
        "validation@test.com",
    )

    invoice = Invoice(
        firm_id=user.firm_id,
        matter_id=1,
        invoice_no="TEST-001",
        invoice_date=date(2026, 8, 1),
        total_amount=5000.00,

        status="processing",
        confidence_score=0.95,
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    token = create_token(user)
    response = client.post(
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

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "auto_approved"
    assert data["status"] == "approved"


def test_invalid_invoice_goes_to_review(
    client,
    db,
):
    user = create_user(
        db,
        "reviewroute@test.com",
    )

    invoice = Invoice(
        firm_id=user.firm_id,
        matter_id=1,
        invoice_no="TEST-002",
        invoice_date=date(2026, 8, 1),
        total_amount=5000.00,
        status="processing",
        confidence_score=0.60,
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    token = create_token(user)

    response = client.post(
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

    assert response.status_code == 200

    data = response.json()

    assert data["decision"] == "pending_review"
    assert data["status"] == "pending_review"