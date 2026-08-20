# TODO: review_queue.py
from __future__ import annotations

from sqlalchemy.orm import Session
from app.models.invoice import Invoice

from app.services.invoice import add_audit_log
from app.services.invoice import add_audit_log

REVIEW_STATUSES = [
    "pending_review",
    "clarification_requested",
]


def get_review_queue(
    db: Session,
    firm_id: int,
):
    """
    Return invoices requiring human review
    for the current firm.
    """

    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.firm_id == firm_id,
            Invoice.status.in_(REVIEW_STATUSES),
        )
        .order_by(Invoice.invoice_date.asc())
        .all()
    )

    results = []

    for invoice in invoices:

        results.append(
            {
                "invoice_id": invoice.invoice_id,
                "matter_id": invoice.matter_id,
                "firm_id": invoice.firm_id,
                "invoice_no": invoice.invoice_no,
                "invoice_date": invoice.invoice_date,
                "total_amount": invoice.total_amount,
                "status": invoice.status,
                "confidence_score": invoice.confidence_score,
                "budget_valid": invoice.budget_valid,
                "duplicate_flag": invoice.duplicate_flag,
                "validation_status": invoice.validation_status,
                "validation_message": invoice.validation_message,
                "review_reasons": build_review_reasons(invoice),
            }
        )

    return results


# TODO: review_reason.py

CONFIDENCE_THRESHOLD = 0.85


def build_review_reasons(invoice) -> list[str]:
    """Canonical human-readable reasons an invoice landed in the review queue."""
    reasons: list[str] = []

    confidence = invoice.confidence_score
    if confidence is not None and confidence < CONFIDENCE_THRESHOLD:
        reasons.append("Extraction confidence is below threshold")

    if invoice.budget_valid is False:
        reasons.append("Invoice failed budget validation")

    if invoice.duplicate_flag:
        reasons.append("Possible duplicate invoice detected")

    if not reasons:
        reasons.append("Invoice requires manual review")

    return reasons


# TODO: rejection_service.py



def reject_invoice(
    db: Session,
    invoice: Invoice,
    user_id: int | None = None,
    reason: str = "",
) -> Invoice:
    """Reject a pending-review invoice.

    Canonical implementation — mirrors app.workflow.approval_service so
    review actions (approve / reject / clarify) all live in workflow/.
    """

    if invoice.status != "pending_review":
        raise ValueError("Only invoices pending review can be rejected.")
    if not reason.strip():
        raise ValueError("Rejection reason is required.")

    old_status = invoice.status
    invoice.status = "rejected"
    db.add(invoice)

    add_audit_log(
        db,
        action="rejected",
        user_id=user_id,
        invoice_id=invoice.invoice_id,
        notes=f"Status changed from '{old_status}' to 'rejected'. Reason: {reason}",
    )

    db.commit()
    db.refresh(invoice)
    return invoice


# TODO: clarification_service.py



def request_clarification(
    db: Session,
    invoice: Invoice,
    user_id: int | None = None,
    reason: str = "",
) -> Invoice:
    """Move a pending-review invoice into 'clarification_requested'.

    Canonical implementation — mirrors app.workflow.approval_service so
    review actions (approve / reject / clarify) all live in workflow/.
    """
    if invoice.status != "pending_review":
        raise ValueError(
            "Clarification can only be requested for invoices pending review."
        )
    if not reason.strip():
        raise ValueError("Clarification reason is required.")

    old_status = invoice.status
    invoice.status = "clarification_requested"
    db.add(invoice)

    add_audit_log(
        db,
        action="clarification_requested",
        user_id=user_id,
        invoice_id=invoice.invoice_id,
        notes=f"Status changed from '{old_status}' to 'clarification_requested'. Reason: {reason}",
    )

    db.commit()
    db.refresh(invoice)
    return invoice


# TODO: approval_service.py


# add near the top of the file
AUTO_APPROVABLE_STATUSES = {"submitted", "pending_review"}


def post_approved_invoice_to_budget(
    db: Session,
    invoice: Invoice,
) -> dict:

    from app.models import Budget, BudgetLedger

    budget = db.query(Budget).filter(Budget.matter_id == invoice.matter_id).first()

    if budget is None:
        return {
            "invoice_id": invoice.invoice_id,
            "amount_posted": invoice.total_amount,
            "status": "no_budget_configured",
        }

    existing = (
        db.query(BudgetLedger)
        .filter(
            BudgetLedger.invoice_id == invoice.invoice_id,
            BudgetLedger.entry_type == "invoice_approved",
        )
        .first()
    )

    if existing is None:

        db.add(
            BudgetLedger(
                budget_id=budget.budget_id,
                invoice_id=invoice.invoice_id,
                amount=invoice.total_amount,
                entry_type="invoice_approved",
            )
        )

    return {
        "invoice_id": invoice.invoice_id,
        "amount_posted": invoice.total_amount,
        "status": "posted",
    }


def auto_approve_invoice(
    db: Session,
    invoice: Invoice,
) -> Invoice:
    """
    System-generated approval.

    Used only when the LangGraph validation rules
    have determined that the invoice qualifies
    for automatic approval.
    """

    if invoice.status != "submitted":
        raise ValueError("Only submitted invoices can be auto-approved.")

    budget_result = post_approved_invoice_to_budget(
        db=db,
        invoice=invoice,
    )

    old_status = invoice.status

    invoice.status = "approved"

    db.add(invoice)

    note = (
        f"Status changed from '{old_status}' "
        f"to 'approved' automatically. "
        f"Budget: {budget_result['status']}."
    )

    add_audit_log(
        db=db,
        action="auto_approved",
        user_id=-1,
        invoice_id=invoice.invoice_id,
        notes=note,
    )

    db.commit()
    db.refresh(invoice)

    return invoice


def approve_invoice(
    db: Session,
    invoice: Invoice,
    user_id: int | None = None,
    notes: str | None = None,
) -> Invoice:

    if invoice.status != "pending_review":
        raise ValueError("Only invoices pending review can be approved.")

    budget_result = post_approved_invoice_to_budget(
        db=db,
        invoice=invoice,
    )

    old_status = invoice.status

    invoice.status = "approved"

    db.add(invoice)

    audit_note = f"Status changed from '{old_status}' " f"to 'approved'."

    if notes:
        audit_note += f" Reason: {notes}"

    audit_note += f" Budget: {budget_result['status']}."

    add_audit_log(
        db=db,
        action="approved",
        user_id=user_id,
        invoice_id=invoice.invoice_id,
        notes=audit_note,
    )

    db.commit()
    db.refresh(invoice)

    return invoice
