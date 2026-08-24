from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Invoice
from app.services.budget import (
    get_invoice_budget_context,
    post_approved_invoice_to_budget,
)
from app.services.invoice import add_audit_log


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
    Human approval.

    Product rules:
      1. A matter with no budget cannot be approved.
      2. An invoice within budget can be approved normally.
      3. An over-budget invoice can be approved as a human override.
      4. An over-budget override requires a non-empty reason.
      5. Every approval is posted to BudgetLedger exactly once.
    """

    if invoice.status != "pending_review":
        raise ValueError(
            "Only invoices pending review can be approved."
        )

    budget_context = get_invoice_budget_context(
        db=db,
        invoice=invoice,
    )

    if not budget_context["has_budget"]:
        raise ValueError(
            "Cannot approve this invoice because the matter has no configured budget. "
            "Create a budget first, then re-run the review."
        )

    override_required = budget_context["projected_over_budget"]
    clean_notes = (notes or "").strip()

    if override_required and not clean_notes:
        raise ValueError(
            "Approval reason is required when overriding the remaining budget."
        )

    budget_result = post_approved_invoice_to_budget(
        db=db,
        invoice=invoice,
    )

    old_status = invoice.status
    invoice.status = "approved"

    summary = budget_result["summary"]

    if override_required:
        action = "approved_budget_override"
        audit_note = (
            f"Status changed from '{old_status}' to 'approved' using a budget override. "
            f"Reason: {clean_notes} "
            f"Budget utilization is now {summary['pct_used']:.1f}%. "
            f"Remaining budget is ${summary['remaining']:,.2f}."
        )
    else:
        action = "approved"
        audit_note = (
            f"Status changed from '{old_status}' to 'approved'. "
            f"Budget utilization is now {summary['pct_used']:.1f}%. "
            f"Remaining budget is ${summary['remaining']:,.2f}."
        )

        if clean_notes:
            audit_note += f" Reviewer notes: {clean_notes}"

    add_audit_log(
        db=db,
        action=action,
        user_id=user_id if user_id is not None else -1,
        invoice_id=invoice.invoice_id,
        notes=audit_note,
    )

    db.commit()
    db.refresh(invoice)

    return invoice