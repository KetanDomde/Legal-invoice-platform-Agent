from __future__ import annotations
 
from sqlalchemy import func
from sqlalchemy.orm import Session
 
from app.models import Alert, AuditLog, Budget, BudgetLedger, Invoice
from app.models import User
 
from app.schemas.invoice_extraction import ExtractedInvoice
from datetime import datetime
from typing import Any
from app.logger_config import request_id_ctx

from app.services.budget import (
    get_budget_summary as get_canonical_budget_summary,
    post_approved_invoice_to_budget,
)


CONFIDENCE_THRESHOLD = 0.85
AUTO_APPROVE = "auto_approved"
HUMAN_REVIEW = "pending_review"
 
 
def add_audit_log(
    db: Session,
    *,
    action: str,
    user_id: int,
    invoice_id: int | None = None,
    notes: str | None = None,
    request_id: str | None = None,
) -> AuditLog:
    """Add an AuditLog row. `user_id` is required; use -1 for system actions."""
    if user_id is None:
        raise ValueError("user_id is required for audit logs; use -1 for system actions")
    if request_id is None:
        try:
            request_id = request_id_ctx.get()
        except Exception:
            request_id = None
 
    log = AuditLog(
        action=action,
        user_id=user_id,
        invoice_id=invoice_id,
        notes=notes,
        request_id=request_id,
    )
    db.add(log)
    return log


# def get_budget_summary(db: Session, matter_id: int) -> dict:
#     budget = db.query(Budget).filter(Budget.matter_id == matter_id).first()
#     if budget is None:
#         raise ValueError(f"No budget found for matter_id={matter_id}")

#     utilized = (
#         db.query(func.coalesce(func.sum(Invoice.total_amount), 0))
#         .filter(
#             Invoice.matter_id == matter_id,
#             Invoice.status == "approved",
#         )
#         .scalar()
#     )
#     utilized = float(utilized or 0)
#     total = float(budget.allocated_amt)
#     remaining = total - utilized
#     pct_used = (utilized / total * 100) if total else 100.0

#     return {
#         "budget": budget,
#         "utilized": utilized,
#         "allocated": total,
#         "remaining": remaining,
#         "pct_used": pct_used,
#         "threshold_pct": float(budget.threshold_pct),
#     }

def get_budget_summary(db: Session, matter_id: int) -> dict:
    """
    Backward-compatible wrapper around the canonical budget service.

    Existing callers can keep using this function, but utilization is now
    calculated from BudgetLedger rather than from Invoice.status.
    """

    summary = get_canonical_budget_summary(db, matter_id)

    if not summary["has_budget"]:
        raise ValueError(
            f"No budget found for matter_id={matter_id}"
        )

    return summary


def find_duplicate_invoice(
    db: Session,
    *,
    matter_id: int,
    invoice_no: str | None,
    total_amount: float,
    exclude_invoice_id: int | None = None,
) -> Invoice | None:
    # Business duplicate key: same matter + same invoice number. Different
    # matters may legitimately reuse invoice numbering.
    if not invoice_no:
        return None
    query = db.query(Invoice).filter(
        Invoice.matter_id == matter_id,
        Invoice.invoice_no == invoice_no,
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
    """
    Run invoice validation.

    Budget validity is always calculated from the canonical BudgetLedger
    summary. A caller cannot mark a missing or exceeded budget as valid.
    The budget_valid argument is kept only for backward compatibility with
    older callers and is intentionally ignored.
    """

    confidence = (
        invoice.confidence_score
        if confidence_score is None
        else confidence_score
    )

    budget = get_canonical_budget_summary(
        db,
        invoice.matter_id,
    )

    has_budget = budget["has_budget"]

    if not has_budget:
        budget_ok = False
        remaining_budget = 0.0
    else:
        remaining_budget = budget["remaining"]
        budget_ok = (
            float(invoice.total_amount or 0)
            <= remaining_budget
        )

    duplicate = None

    if duplicate_flag is None:
        duplicate = find_duplicate_invoice(
            db,
            matter_id=invoice.matter_id,
            invoice_no=invoice.invoice_no,
            total_amount=float(invoice.total_amount),
            exclude_invoice_id=invoice.invoice_id,
        )
        duplicate_flag_value = duplicate is not None
    else:
        duplicate_flag_value = bool(duplicate_flag)

    reasons: list[str] = []

    if not has_budget:
        reasons.append(
            "No budget is configured for this matter. "
            "The invoice must be reviewed after a budget is created."
        )

    elif not budget_ok:
        shortfall = abs(
            remaining_budget - float(invoice.total_amount or 0)
        )

        reasons.append(
            f"Invoice amount {float(invoice.total_amount):.2f} "
            f"exceeds remaining budget {remaining_budget:.2f} "
            f"by {shortfall:.2f}."
        )

    if duplicate_flag_value:
        reasons.append("Duplicate invoice detected.")

    if (
        confidence is not None
        and confidence < CONFIDENCE_THRESHOLD
    ):
        reasons.append(
            f"Extraction confidence {confidence:.2f} is below "
            f"threshold {CONFIDENCE_THRESHOLD:.2f}."
        )

    validation_passed = (
        has_budget
        and budget_ok
        and not duplicate_flag_value
    )

    decision = (
        AUTO_APPROVE
        if (
            validation_passed
            and confidence is not None
            and confidence >= CONFIDENCE_THRESHOLD
        )
        else HUMAN_REVIEW
    )

    if not reasons:
        reasons.append(
            "All validation checks passed."
            if decision == AUTO_APPROVE
            else "Invoice requires manual review."
        )

    return {
        "validation_passed": validation_passed,
        "has_budget": has_budget,
        "budget_ok": budget_ok,
        "remaining_budget": remaining_budget,
        "budget_utilized": budget["utilized"],
        "budget_allocated": budget["allocated"],
        "budget_pct_used": budget["pct_used"],
        "threshold_pct": budget["threshold_pct"],
        "duplicate": duplicate_flag_value,
        "duplicate_invoice_id": (
            duplicate.invoice_id
            if duplicate
            else None
        ),
        "confidence_score": confidence,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "decision": decision,
        "reasons": reasons,
    }

# def validate_invoice(
#     db: Session,
#     invoice: Invoice,
#     confidence_score: float | None = None,
#     budget_valid: bool | None = None,
#     duplicate_flag: bool | None = None,
# ) -> dict:
#     """Run invoice validation synchronously.

#     API callers may provide the already-computed budget/duplicate flags.
#     When omitted, the service calculates them from the database.
#     """
#     confidence = invoice.confidence_score if confidence_score is None else confidence_score

#     budget = None
#     if budget_valid is None:
#         try:
#             budget = get_budget_summary(db, invoice.matter_id)
#             budget_ok = float(invoice.total_amount) <= budget["remaining"]
#             remaining_budget = budget["remaining"]
#         except ValueError:
#             # A matter without a configured budget is not a validation error for
#             # the review API. Treat it as budget-valid and let explicit callers
#             # supply budget_valid when they have an external budget decision.
#             budget_ok = True
#             remaining_budget = 0.0
#     else:
#         budget_ok = bool(budget_valid)
#         if budget_valid:
#             try:
#                 budget = get_budget_summary(db, invoice.matter_id)
#                 remaining_budget = budget["remaining"]
#             except ValueError:
#                 remaining_budget = float(invoice.total_amount)
#         else:
#             remaining_budget = 0.0

#     duplicate = None
#     if duplicate_flag is None:
#         duplicate = find_duplicate_invoice(
#             db,
#             firm_id=invoice.firm_id,
#             invoice_no=invoice.invoice_no,
#             total_amount=float(invoice.total_amount),
#             exclude_invoice_id=invoice.invoice_id,
#         )
#         duplicate_flag_value = duplicate is not None
#     else:
#         duplicate_flag_value = bool(duplicate_flag)

#     reasons: list[str] = []
#     if not budget_ok:
#         reasons.append(
#             f"Invoice amount {float(invoice.total_amount):.2f} exceeds remaining budget {remaining_budget:.2f}."
#         )
#     if duplicate_flag_value:
#         reasons.append("Duplicate invoice detected.")
#     if confidence is not None and confidence < CONFIDENCE_THRESHOLD:
#         reasons.append(
#             f"Extraction confidence {confidence:.2f} is below threshold {CONFIDENCE_THRESHOLD:.2f}."
#         )

#     validation_passed = budget_ok and not duplicate_flag_value
#     decision = AUTO_APPROVE if validation_passed and confidence is not None and confidence >= CONFIDENCE_THRESHOLD else HUMAN_REVIEW

#     if not reasons:
#         reasons.append("All validation checks passed." if decision == AUTO_APPROVE else "Invoice requires manual review.")

#     return {
#         "validation_passed": validation_passed,
#         "budget_ok": budget_ok,
#         "remaining_budget": remaining_budget,
#         "duplicate": duplicate_flag_value,
#         "duplicate_invoice_id": duplicate.invoice_id if duplicate else None,
#         "confidence_score": confidence,
#         "confidence_threshold": CONFIDENCE_THRESHOLD,
#         "decision": decision,
#         "reasons": reasons,
#     }


# def validate_and_route_invoice(
#     db: Session,
#     invoice: Invoice,
#     confidence_score: float | None = None,
#     budget_valid: bool | None = None,
#     duplicate_flag: bool | None = None,
# ) -> dict:
#     result = validate_invoice(
#         db, invoice, confidence_score, budget_valid, duplicate_flag
#     )

#     invoice.confidence_score = result["confidence_score"]
#     invoice.budget_valid = result["budget_ok"]
#     invoice.duplicate_flag = result["duplicate"]
#     invoice.validation_status = "passed" if result["validation_passed"] else "failed"
#     invoice.validation_message = "; ".join(result["reasons"])
#     invoice.status = "approved" if result["decision"] == AUTO_APPROVE else "pending_review"

#     add_audit_log(
#         db,
#         action="auto_approved" if result["decision"] == AUTO_APPROVE else "validated",
#         user_id=-1,
#         invoice_id=invoice.invoice_id,
#         notes=invoice.validation_message,
#     )
#     db.commit()
#     db.refresh(invoice)
#     return result

def validate_and_route_invoice(
    db: Session,
    invoice: Invoice,
    confidence_score: float | None = None,
    budget_valid: bool | None = None,
    duplicate_flag: bool | None = None,
) -> dict:
    """
    Validate an invoice and route it through the canonical approval flow.

    Auto-approved invoices must always go through approval_service so that
    BudgetLedger and alerts stay synchronized.
    """

    result = validate_invoice(
        db,
        invoice,
        confidence_score,
        budget_valid,
        duplicate_flag,
    )
 
    invoice.confidence_score = result["confidence_score"]
    invoice.budget_valid = result["budget_ok"]
    invoice.duplicate_flag = result["duplicate"]
    invoice.validation_status = (
        "passed"
        if result["validation_passed"]
        else "failed"
    )
    invoice.validation_message = "; ".join(
        result["reasons"]
    )

    if result["decision"] == AUTO_APPROVE:
        # Keep the invoice in submitted state so the canonical auto-approval
        # service can post the ledger entry and then approve it.
        invoice.status = "submitted"
        db.flush()

        from app.workflow.approval_service import (
            auto_approve_invoice,
        )

        auto_approve_invoice(
            db=db,
            invoice=invoice,
        )

    else:
        invoice.status = "pending_review"

        add_audit_log(
            db,
            action="validated",
            user_id=-1,
            invoice_id=invoice.invoice_id,
            notes=invoice.validation_message,
        )

        db.commit()
        db.refresh(invoice)

    return result

def _post_budget_entry(
    db: Session,
    invoice: Invoice,
) -> None:
    """
    Backward-compatible wrapper.

    All budget posting now goes through the central budget service.
    """

    post_approved_invoice_to_budget(
        db=db,
        invoice=invoice,
    )

# def _post_budget_entry(db: Session, invoice: Invoice) -> None:
#     budget = db.query(Budget).filter(Budget.matter_id == invoice.matter_id).first()
#     if budget is None:
#         return

#     already_posted = (
#         db.query(BudgetLedger)
#         .filter(
#             BudgetLedger.invoice_id == invoice.invoice_id,
#             BudgetLedger.entry_type == "invoice_approved",
#         )
#         .first()
#     )
#     if already_posted:
#         return

#     db.add(
#         BudgetLedger(
#             budget_id=budget.budget_id,
#             invoice_id=invoice.invoice_id,
#             amount=invoice.total_amount,
#             entry_type="invoice_approved",
#         )
#     )

#     summary = get_budget_summary(db, invoice.matter_id)
#     projected_pct = summary["pct_used"]
#     if projected_pct >= summary["threshold_pct"]:
#         db.add(
#             Alert(
#                 budget_id=budget.budget_id,
#                 type="budget_threshold",
#                 message=(
#                     f"Matter {invoice.matter_id} will reach approximately "
#                     f"{projected_pct:.1f}% budget utilization after invoice "
#                     f"{invoice.invoice_id}."
#                 ),
#             )
#         )


def approve_invoice(db: Session, invoice: Invoice, user_id: int, notes: str | None = None) -> Invoice:
    # Canonical approval implementation lives in workflow/approval_service.py.
    from app.workflow.approval_service import approve_invoice as _approve_invoice
    return _approve_invoice(db=db, invoice=invoice, user_id=user_id, notes=notes)
 
def reject_invoice(db: Session, invoice: Invoice, user_id: int, reason: str) -> Invoice:
    # Canonical rejection implementation lives in workflow/rejection_service.py.
    from app.services.review_service import reject_invoice as _reject_invoice
    return _reject_invoice(db=db, invoice=invoice, user_id=user_id, reason=reason)
 
 
def request_clarification(db: Session, invoice: Invoice, user_id: int, reason: str) -> Invoice:
    # Canonical clarification implementation lives in workflow/clarification_service.py.
    from app.services.review_service import request_clarification as _request_clarification
    return _request_clarification(db=db, invoice=invoice, user_id=user_id, reason=reason)
 
 
def get_review_reasons(invoice: Invoice) -> list[str]:
    """Return actionable reasons an administrator can resolve.

    Prefer the server-generated validation message because it preserves the
    exact failing rules instead of reducing every case to a generic label.
    """
    reasons: list[str] = []
    if invoice.validation_message:
        reasons.extend(
            [part.strip() for part in invoice.validation_message.split(";") if part.strip()]
        )

    if invoice.budget_valid is False and not any("budget" in r.lower() for r in reasons):
        reasons.append("Invoice amount exceeds the remaining budget.")
    if invoice.duplicate_flag and not any("duplicate" in r.lower() for r in reasons):
        reasons.append("Possible duplicate invoice detected.")
    if (
        invoice.confidence_score is not None
        and invoice.confidence_score < CONFIDENCE_THRESHOLD
        and not any("confidence" in r.lower() for r in reasons)
    ):
        reasons.append(
            f"Extraction confidence {invoice.confidence_score:.2f} is below the required {CONFIDENCE_THRESHOLD:.2f}."
        )

    # De-duplicate while preserving order.
    reasons = list(dict.fromkeys(reasons))
    return reasons or ["Invoice requires manual review."]


def get_review_queue(db: Session, firm_id: int | None) -> list[dict]:
    query = db.query(Invoice).filter(
        Invoice.status.in_([HUMAN_REVIEW, "clarification_requested"])
    )
    if firm_id is not None:
        query = query.filter(Invoice.firm_id == firm_id)
    invoices = query.order_by(Invoice.invoice_date.asc().nulls_last(), Invoice.invoice_id.asc()).all()
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
 
 
def get_invoice_for_review(db: Session, invoice_id: int, firm_id: int | None) -> Invoice:
    query = db.query(Invoice).filter(Invoice.invoice_id == invoice_id)
    if firm_id is not None:
        query = query.filter(Invoice.firm_id == firm_id)
    invoice = query.first()
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