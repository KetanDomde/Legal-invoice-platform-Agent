from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Alert, AuditLog, Budget, BudgetLedger, Invoice
from app.models import User

from app.schemas.invoice_extraction import ExtractedInvoice
from datetime import datetime
from typing import Any


CONFIDENCE_THRESHOLD = 0.85
AUTO_APPROVE = "auto_approved"
HUMAN_REVIEW = "pending_review"


def add_audit_log(
    db: Session,
    *,
    action: str,
    user_id: int | None = None,
    invoice_id: int | None = None,
    notes: str | None = None,
) -> AuditLog:
    log = AuditLog(
        action=action,
        user_id=user_id,
        invoice_id=invoice_id,
        notes=notes,
    )
    db.add(log)
    return log


def get_budget_summary(db: Session, matter_id: int) -> dict:
    budget = db.query(Budget).filter(Budget.matter_id == matter_id).first()
    if budget is None:
        raise ValueError(f"No budget found for matter_id={matter_id}")

    utilized = (
        db.query(func.coalesce(func.sum(Invoice.total_amount), 0))
        .filter(
            Invoice.matter_id == matter_id,
            Invoice.status == "approved",
        )
        .scalar()
    )
    utilized = float(utilized or 0)
    total = float(budget.allocated_amt)
    remaining = total - utilized
    pct_used = (utilized / total * 100) if total else 100.0

    return {
        "budget": budget,
        "utilized": utilized,
        "allocated": total,
        "remaining": remaining,
        "pct_used": pct_used,
        "threshold_pct": float(budget.threshold_pct),
    }


def find_duplicate_invoice(
    db: Session,
    *,
    firm_id: int,
    invoice_no: str,
    total_amount: float,
    exclude_invoice_id: int | None = None,
) -> Invoice | None:
    query = db.query(Invoice).filter(
        Invoice.firm_id == firm_id,
        Invoice.invoice_no == invoice_no,
        # removing amount for finding duplicate
        # Invoice.total_amount == total_amount, 
    )
    if exclude_invoice_id is not None:
        query = query.filter(Invoice.invoice_id != exclude_invoice_id)
    return query.first()


def validate_invoice(
    db: Session,
    invoice: Invoice,
    confidence_score: float | None = None,
    budget_valid: bool | None = None,
    duplicate_flag: bool | None = None,
) -> dict:
    """Run invoice validation synchronously.

    API callers may provide the already-computed budget/duplicate flags.
    When omitted, the service calculates them from the database.
    """
    confidence = invoice.confidence_score if confidence_score is None else confidence_score

    budget = None
    if budget_valid is None:
        try:
            budget = get_budget_summary(db, invoice.matter_id)
            budget_ok = float(invoice.total_amount) <= budget["remaining"]
            remaining_budget = budget["remaining"]
        except ValueError:
            # A matter without a configured budget is not a validation error for
            # the review API. Treat it as budget-valid and let explicit callers
            # supply budget_valid when they have an external budget decision.
            budget_ok = True
            remaining_budget = 0.0
    else:
        budget_ok = bool(budget_valid)
        if budget_valid:
            try:
                budget = get_budget_summary(db, invoice.matter_id)
                remaining_budget = budget["remaining"]
            except ValueError:
                remaining_budget = float(invoice.total_amount)
        else:
            remaining_budget = 0.0

    duplicate = None
    if duplicate_flag is None:
        duplicate = find_duplicate_invoice(
            db,
            firm_id=invoice.firm_id,
            invoice_no=invoice.invoice_no,
            total_amount=float(invoice.total_amount),
            exclude_invoice_id=invoice.invoice_id,
        )
        duplicate_flag_value = duplicate is not None
    else:
        duplicate_flag_value = bool(duplicate_flag)

    reasons: list[str] = []
    if not budget_ok:
        reasons.append(
            f"Invoice amount {float(invoice.total_amount):.2f} exceeds remaining budget {remaining_budget:.2f}."
        )
    if duplicate_flag_value:
        reasons.append("Duplicate invoice detected.")
    if confidence is not None and confidence < CONFIDENCE_THRESHOLD:
        reasons.append(
            f"Extraction confidence {confidence:.2f} is below threshold {CONFIDENCE_THRESHOLD:.2f}."
        )

    validation_passed = budget_ok and not duplicate_flag_value
    decision = AUTO_APPROVE if validation_passed and confidence is not None and confidence >= CONFIDENCE_THRESHOLD else HUMAN_REVIEW

    if not reasons:
        reasons.append("All validation checks passed." if decision == AUTO_APPROVE else "Invoice requires manual review.")

    return {
        "validation_passed": validation_passed,
        "budget_ok": budget_ok,
        "remaining_budget": remaining_budget,
        "duplicate": duplicate_flag_value,
        "duplicate_invoice_id": duplicate.invoice_id if duplicate else None,
        "confidence_score": confidence,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "decision": decision,
        "reasons": reasons,
    }


def validate_and_route_invoice(
    db: Session,
    invoice: Invoice,
    confidence_score: float | None = None,
    budget_valid: bool | None = None,
    duplicate_flag: bool | None = None,
) -> dict:
    result = validate_invoice(
        db, invoice, confidence_score, budget_valid, duplicate_flag
    )

    invoice.confidence_score = result["confidence_score"]
    invoice.budget_valid = result["budget_ok"]
    invoice.duplicate_flag = result["duplicate"]
    invoice.validation_status = "passed" if result["validation_passed"] else "failed"
    invoice.validation_message = "; ".join(result["reasons"])
    invoice.status = "approved" if result["decision"] == AUTO_APPROVE else "pending_review"

    add_audit_log(
        db,
        action="auto_approved" if result["decision"] == AUTO_APPROVE else "validated",
        invoice_id=invoice.invoice_id,
        notes=invoice.validation_message,
    )
    db.commit()
    db.refresh(invoice)
    return result


def _post_budget_entry(db: Session, invoice: Invoice) -> None:
    budget = db.query(Budget).filter(Budget.matter_id == invoice.matter_id).first()
    if budget is None:
        return

    already_posted = (
        db.query(BudgetLedger)
        .filter(
            BudgetLedger.invoice_id == invoice.invoice_id,
            BudgetLedger.entry_type == "invoice_approved",
        )
        .first()
    )
    if already_posted:
        return

    db.add(
        BudgetLedger(
            budget_id=budget.budget_id,
            invoice_id=invoice.invoice_id,
            amount=invoice.total_amount,
            entry_type="invoice_approved",
        )
    )

    summary = get_budget_summary(db, invoice.matter_id)
    projected_pct = summary["pct_used"]
    if projected_pct >= summary["threshold_pct"]:
        db.add(
            Alert(
                budget_id=budget.budget_id,
                type="budget_threshold",
                message=(
                    f"Matter {invoice.matter_id} will reach approximately "
                    f"{projected_pct:.1f}% budget utilization after invoice "
                    f"{invoice.invoice_id}."
                ),
            )
        )


def approve_invoice(db: Session, invoice: Invoice, user_id: int, notes: str | None = None) -> Invoice:
    # Canonical approval implementation lives in workflow/approval_service.py.
    from app.workflow.approval_service import approve_invoice as _approve_invoice
    return _approve_invoice(db=db, invoice=invoice, user_id=user_id, notes=notes)

def reject_invoice(db: Session, invoice: Invoice, user_id: int, reason: str) -> Invoice:
    if invoice.status != "pending_review":
        raise ValueError("Only invoices pending review can be rejected.")
    if not reason.strip():
        raise ValueError("Rejection reason is required.")

    old_status = invoice.status
    invoice.status = "rejected"
    add_audit_log(
        db,
        action="rejected",
        user_id=user_id,
        invoice_id=invoice.invoice_id,
        notes=_status_note(old_status, invoice.status, reason),
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def request_clarification(db: Session, invoice: Invoice, user_id: int, reason: str) -> Invoice:
    if invoice.status != "pending_review":
        raise ValueError("Clarification can only be requested for invoices pending review.")
    if not reason.strip():
        raise ValueError("Clarification reason is required.")

    old_status = invoice.status
    invoice.status = "clarification_requested"
    add_audit_log(
        db,
        action="clarification_requested",
        user_id=user_id,
        invoice_id=invoice.invoice_id,
        notes=_status_note(old_status, invoice.status, reason),
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def get_review_reasons(invoice: Invoice) -> list[str]:
    reasons: list[str] = []
    if invoice.confidence_score is not None and invoice.confidence_score < CONFIDENCE_THRESHOLD:
        reasons.append("Extraction confidence is below threshold.")
    if invoice.budget_valid is False:
        reasons.append("Invoice failed budget validation.")
    if invoice.duplicate_flag:
        reasons.append("Possible duplicate invoice detected.")
    if not reasons:
        reasons.append("Invoice requires manual review.")
    return reasons


def get_review_queue(db: Session, firm_id: int) -> list[dict]:
    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.firm_id == firm_id,
            Invoice.status.in_([HUMAN_REVIEW.replace("human_review", "pending_review"), "clarification_requested"]),
        )
        .order_by(Invoice.invoice_date.asc().nulls_last(), Invoice.invoice_id.asc())
        .all()
    )
    return [
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
        for invoice in invoices
    ]


def get_invoice_for_review(db: Session, invoice_id: int, firm_id: int) -> Invoice:
    invoice = (
        db.query(Invoice)
        .filter(Invoice.invoice_id == invoice_id, Invoice.firm_id == firm_id)
        .first()
    )
    if invoice is None:
        raise ValueError("Invoice not found.")
    return invoice


def _status_note(old_status: str, new_status: str, reason: str | None = None) -> str:
    note = f"Status changed from '{old_status}' to '{new_status}'."
    if reason:
        note += f" Reason: {reason}"
    return note


def get_duplicate_invoice(inv: Invoice) -> ExtractedInvoice | None:
    return ExtractedInvoice.model_validate(inv)


def diff_invoices(
    original: ExtractedInvoice, duplicate: ExtractedInvoice
) -> dict[str, Any]:
    """Compares two ExtractedInvoice instances and returns a structured diff

    containing only the changed fields with their original and modified values.
    """
    diff: dict[str, Any] = {}

    # 1. Compare top-level scalar fields
    scalar_fields = ["invoice_no", "invoice_date", "total_amount"]
    for field in scalar_fields:
        orig_val = getattr(original, field)
        dupe_val = getattr(duplicate, field)
        if orig_val != dupe_val:
            diff[field] = {
                "changed": True,
                "original": orig_val,
                "duplicate": dupe_val,
            }

    # 2. Compare line items
    orig_items = original.line_items
    dupe_items = duplicate.line_items
    line_item_diffs = []

    max_len = max(len(orig_items), len(dupe_items))
    line_item_fields = ["timekeeper", "hours", "rate", "amount"]

    for i in range(max_len):
        # Case A: Item present in both
        if i < len(orig_items) and i < len(dupe_items):
            item_orig = orig_items[i]
            item_dupe = dupe_items[i]
            item_changes = {}

            for field in line_item_fields:
                val_orig = getattr(item_orig, field)
                val_dupe = getattr(item_dupe, field)
                if val_orig != val_dupe:
                    item_changes[field] = {
                        "changed": True,
                        "original": val_orig,
                        "duplicate": val_dupe,
                    }

            if item_changes:
                line_item_diffs.append({"index": i, "changes": item_changes})

        # Case B: Item deleted in duplicate
        elif i < len(orig_items):
            line_item_diffs.append(
                {
                    "index": i,
                    "status": "removed",
                    "original": orig_items[i].model_dump(),
                }
            )

        # Case C: Item added in duplicate
        else:
            line_item_diffs.append(
                {
                    "index": i,
                    "status": "added",
                    "duplicate": dupe_items[i].model_dump(),
                }
            )

    if line_item_diffs:
        diff["line_items"] = line_item_diffs

    return diff