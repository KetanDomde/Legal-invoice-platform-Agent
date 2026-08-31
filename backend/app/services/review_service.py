from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.services.invoice import (
    add_audit_log,
    get_review_reasons,
    validate_invoice,
)


REVIEW_STATUSES = [
    "pending_review",
    "clarification_required",
]


def get_review_queue(
    db: Session,
    firm_id: int | None,
):
    """
    Return invoices requiring human review
    for the current firm.
    """

    query = db.query(Invoice).filter(
        Invoice.status.in_(REVIEW_STATUSES)
    )

    # Global users can see all firms.
    if firm_id is not None:
        query = query.filter(
            Invoice.firm_id == firm_id
        )

    invoices = (
        query
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
                "total_amount": float(invoice.total_amount),
                "status": invoice.status,
                "confidence_score": invoice.confidence_score,
                "budget_valid": invoice.budget_valid,
                "duplicate_flag": invoice.duplicate_flag,
                "validation_status": invoice.validation_status,
                "validation_message": invoice.validation_message,
                "review_reasons": get_review_reasons(invoice),
            }
        )

    return results


def reject_invoice(
    db: Session,
    invoice: Invoice,
    user_id: int | None = None,
    reason: str = "",
) -> Invoice:
    """
    Reject an invoice from the human review queue.

    Rejection:
        pending_review
            ↓
        rejected
            ↓
        workflow stops
    """

    if invoice.status != "pending_review":
        raise ValueError(
            "Only invoices pending review can be rejected."
        )

    clean_reason = (reason or "").strip()

    if not clean_reason:
        raise ValueError(
            "Rejection reason is required."
        )

    old_status = invoice.status

    invoice.status = "rejected"

    db.add(invoice)

    add_audit_log(
        db=db,
        action="rejected",
        user_id=user_id if user_id is not None else -1,
        invoice_id=invoice.invoice_id,
        notes=(
            f"Status changed from '{old_status}' to 'rejected'. "
            f"Reason: {clean_reason}"
        ),
    )

    db.commit()
    db.refresh(invoice)

    return invoice


def request_clarification(
    db: Session,
    invoice: Invoice,
    user_id: int | None = None,
    reason: str = "",
) -> Invoice:
    """
    Request additional information from the requester.

    Flow:
        pending_review
            ↓
        clarification_required
            ↓
        workflow pauses
    """

    if invoice.status != "pending_review":
        raise ValueError(
            "Clarification can only be requested "
            "for invoices pending review."
        )

    clean_reason = (reason or "").strip()

    if not clean_reason:
        raise ValueError(
            "Clarification question/comment is required."
        )

    old_status = invoice.status

    invoice.status = "clarification_required"

    db.add(invoice)

    add_audit_log(
        db=db,
        action="clarification_required",
        user_id=user_id if user_id is not None else -1,
        invoice_id=invoice.invoice_id,
        notes=(
            f"Status changed from '{old_status}' "
            f"to 'clarification_required'. "
            f"Question/comment: {clean_reason}"
        ),
    )

    db.commit()
    db.refresh(invoice)

    return invoice


def resolve_clarification(
    db: Session,
    invoice: Invoice,
    user_id: int | None = None,
    information: str = "",
) -> Invoice:
    """
    Handle information received after clarification.

    IMPORTANT:
    The invoice is revalidated and returned to the human
    review queue. It is NOT automatically approved.
    """

    if invoice.status != "clarification_required":
        raise ValueError(
            "Only invoices requiring clarification "
            "can be resolved."
        )

    clean_information = (information or "").strip()

    if not clean_information:
        raise ValueError(
            "Clarification information is required."
        )

    # ---------------------------------------------------------
    # 1. Save the clarification information in audit history
    # ---------------------------------------------------------

    add_audit_log(
        db=db,
        action="clarification_provided",
        user_id=user_id if user_id is not None else -1,
        invoice_id=invoice.invoice_id,
        notes=(
            "Information provided after clarification request: "
            f"{clean_information}"
        ),
    )

    # ---------------------------------------------------------
    # 2. Re-run server-side invoice validation
    # ---------------------------------------------------------

    validation_result = validate_invoice(
        db=db,
        invoice=invoice,
        confidence_score=invoice.confidence_score,
    )

    invoice.budget_valid = validation_result["budget_ok"]

    invoice.duplicate_flag = validation_result["duplicate"]

    invoice.validation_status = (
        "passed"
        if validation_result["validation_passed"]
        else "failed"
    )

    invoice.validation_message = "; ".join(
        validation_result["reasons"]
    )

    # ---------------------------------------------------------
    # 3. NEVER automatically approve after clarification
    # ---------------------------------------------------------

    invoice.status = "pending_review"

    db.add(invoice)

    add_audit_log(
        db=db,
        action="revalidated_after_clarification",
        user_id=user_id if user_id is not None else -1,
        invoice_id=invoice.invoice_id,
        notes=(
            "Invoice was revalidated after clarification "
            "and returned to human review. "
            f"Validation status: "
            f"{invoice.validation_status}. "
            f"Message: "
            f"{invoice.validation_message}"
        ),
    )

    db.commit()
    db.refresh(invoice)

    return invoice