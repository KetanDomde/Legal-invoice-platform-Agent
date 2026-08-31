from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Invoice
from app.services.budget import (
    get_invoice_budget_context,
    post_approved_invoice_to_budget,
)
from app.services.invoice import add_audit_log, validate_invoice


def _apply_validation_result(invoice: Invoice, result: dict) -> None:
    """Refresh the invoice's cached validation fields from a fresh check."""
    invoice.confidence_score = result["confidence_score"]
    invoice.budget_valid = result["budget_ok"]
    invoice.duplicate_flag = result["duplicate"]
    invoice.validation_status = "passed" if result["validation_passed"] else "failed"
    invoice.validation_message = "; ".join(result["reasons"])


def auto_approve_invoice(
    db: Session,
    invoice: Invoice,
) -> Invoice:
    """
    System approval.

    Auto approval is intentionally strict:
      - invoice must be submitted,
      - a budget must exist,
      - the invoice must remain within the allocated budget.

    An over-budget invoice must never reach this path.
    """

    if invoice.status != "submitted":
        raise ValueError(
            "Only submitted invoices can be auto-approved."
        )

    budget_context = get_invoice_budget_context(
        db=db,
        invoice=invoice,
    )

    if not budget_context["has_budget"]:
        raise ValueError(
            "Invoice cannot be auto-approved because this matter has no configured budget."
        )

    if budget_context["projected_over_budget"]:
        raise ValueError(
            "Invoice cannot be auto-approved because it exceeds the remaining budget."
        )

    budget_result = post_approved_invoice_to_budget(
        db=db,
        invoice=invoice,
    )

    old_status = invoice.status
    invoice.status = "approved"

    summary = budget_result["summary"]

    note = (
        f"Status changed from '{old_status}' to 'approved' automatically. "
        f"Budget utilization is now {summary['pct_used']:.1f}%. "
        f"Remaining budget is ${summary['remaining']:,.2f}."
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
    """
    Human approval decision.

    Approval can NEVER bypass duplicate, validation, or budget checks:
      1. The invoice must currently be pending_review.
      2. Duplicate detection and budget adequacy are re-checked at the
         moment of approval via the same canonical validate_invoice() used
         at intake — cached flags from the original review are never
         trusted blindly, since the matter's budget or other invoices may
         have changed since the invoice entered the queue.
      3. If re-validation finds a blocking duplicate or a budget shortfall
         (including a missing budget), the invoice is NOT approved. It is
         kept as an exception in the review queue with refreshed reasons,
         and the blocked attempt is audit logged. There is no reviewer
         override for these checks.
      4. Only when duplicate + budget checks both pass is the invoice
         posted to BudgetLedger (exactly once) and marked approved.
    """

    if invoice.status != "pending_review":
        raise ValueError(
            "Only invoices pending review can be approved."
        )

    # Step 1: re-validate — duplicate + budget are recomputed fresh.
    result = validate_invoice(db, invoice)
    _apply_validation_result(invoice, result)

    blocking_reasons: list[str] = []
    if not result["has_budget"]:
        blocking_reasons.append("No budget is configured for this matter.")
    elif not result["budget_ok"]:
        blocking_reasons.append(
            f"Invoice amount {float(invoice.total_amount):.2f} exceeds "
            f"remaining budget {result['remaining_budget']:.2f}."
        )
    if result["duplicate"]:
        blocking_reasons.append("Duplicate invoice detected.")

    if blocking_reasons:
        old_status = invoice.status
        db.add(invoice)
        add_audit_log(
            db=db,
            action="approval_blocked",
            user_id=user_id if user_id is not None else -1,
            invoice_id=invoice.invoice_id,
            notes=(
                f"Approval attempt on invoice in '{old_status}' was blocked "
                "and sent back to the review queue as an exception. "
                f"Reasons: {'; '.join(blocking_reasons)}"
            ),
        )
        db.commit()
        db.refresh(invoice)
        raise ValueError(
            "Invoice failed re-validation and cannot be approved: "
            + "; ".join(blocking_reasons)
        )

    # Step 2: budget check passed — post to ledger exactly once and approve.
    budget_result = post_approved_invoice_to_budget(
        db=db,
        invoice=invoice,
    )

    old_status = invoice.status
    invoice.status = "approved"

    summary = budget_result["summary"]

    audit_note = (
        f"Status changed from '{old_status}' to 'approved' after re-validation. "
        f"Budget utilization is now {summary['pct_used']:.1f}%. "
        f"Remaining budget is ${summary['remaining']:,.2f}."
    )

    clean_notes = (notes or "").strip()
    if clean_notes:
        audit_note += f" Reviewer notes: {clean_notes}"

    add_audit_log(
        db=db,
        action="approved",
        user_id=user_id if user_id is not None else -1,
        invoice_id=invoice.invoice_id,
        notes=audit_note,
    )

    db.commit()
    db.refresh(invoice)

    return invoice