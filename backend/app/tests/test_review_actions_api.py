from decimal import Decimal

from app.models.user import User
from app.models.invoice import Invoice
from datetime import date
from app.auth.password import hash_password
from app.auth.jwt_handler import create_access_token
from app.models.audit_log import AuditLog


def create_user(
    db,
    email,
    role="editor",
    firm_id=1,
):
    user = User(
        name="Review Tester",
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


def create_invoice(
    db,
    firm_id=1,
    status="pending_review",
):

    invoice = Invoice(
        firm_id=firm_id,
        matter_id=1,
        invoice_no="REVIEW-TEST",
        status=status,
        invoice_date=date(2026, 8, 1),

        total_amount=Decimal("1000.00"),
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return invoice


# =====================================================
# APPROVE
# =====================================================

def test_editor_can_approve(
    client,
    db,
    monkeypatch,
):

    user = create_user(
        db,
        "approve@test.com",
        "editor",
    )

    invoice = create_invoice(
        db,
        user.firm_id,
    )

    def fake_budget_post(
        db,
        invoice,
    ):
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

    token = create_token(user)

    response = client.post(
        f"/review/{invoice.invoice_id}/approve",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
        params={
            "notes": "Looks correct",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "approved"


# =====================================================
# REJECT
# =====================================================

def test_editor_can_reject(
    client,
    db,
):

    user = create_user(
        db,
        "reject@test.com",
        "editor",
    )

    invoice = create_invoice(
        db,
        user.firm_id,
    )

    token = create_token(user)

    response = client.post(
        f"/review/{invoice.invoice_id}/reject",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
        params={
            "reason": "Duplicate invoice",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "rejected"


# =====================================================
# CLARIFY
# =====================================================

def test_editor_can_request_clarification(
    client,
    db,
):

    user = create_user(
        db,
        "clarify@test.com",
        "editor",
    )

    invoice = create_invoice(
        db,
        user.firm_id,
    )

    token = create_token(user)

    response = client.post(
        f"/review/{invoice.invoice_id}/clarify",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
        params={
            "reason": (
                "Supporting document is missing"
            ),
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["status"]
        == "clarification_requested"
    )
    
    
def test_viewer_cannot_approve(
    client,
    db,
):

    user = create_user(
        db,
        "viewer@test.com",
        "viewer",
    )

    invoice = create_invoice(
        db,
        user.firm_id,
    )

    token = create_token(user)

    response = client.post(
        f"/review/{invoice.invoice_id}/approve",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
    )

    assert response.status_code == 403
    
    

def test_user_cannot_review_other_firm_invoice(
    client,
    db,
):

    user = create_user(
        db,
        "firm1@test.com",
        "editor",
        firm_id=1,
    )

    invoice = create_invoice(
        db,
        firm_id=2,
    )

    token = create_token(user)

    response = client.post(
        f"/review/{invoice.invoice_id}/reject",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
        params={
            "reason": "Not our firm",
        },
    )

    assert response.status_code == 404
    
def test_rejection_requires_reason(
    client,
    db,
):

    user = create_user(
        db,
        "rejectreason@test.com",
        "editor",
    )

    invoice = create_invoice(
        db,
        user.firm_id,
    )

    token = create_token(user)

    response = client.post(
        f"/review/{invoice.invoice_id}/reject",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
        params={
            "reason": "",
        },
    )

    assert response.status_code == 400
    

def test_already_approved_invoice_cannot_be_approved(
    client,
    db,
    monkeypatch,
):

    user = create_user(
        db,
        "alreadyapproved@test.com",
        "editor",
    )

    invoice = create_invoice(
        db,
        user.firm_id,
        status="approved",
    )

    def fake_budget_post(
        db,
        invoice,
    ):
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

    token = create_token(user)

    response = client.post(
        f"/review/{invoice.invoice_id}/approve",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
    )

    assert response.status_code == 400
    
    
## extra code for helper

# def create_test_invoice(
#     db,
#     firm_id,
#     matter_id=1,
#     status="pending_review",
# ):
#     invoice = Invoice(
#         firm_id=firm_id,
#         matter_id=matter_id,
#         invoice_no="TEST-INV-001",
#         invoice_date=date(2026, 1, 15),
#         total_amount=Decimal("1000.00"),
#         confidence_score=0.60,
#         status=status,
#     )

#     db.add(invoice)
#     db.commit()
#     db.refresh(invoice)

#     return invoice