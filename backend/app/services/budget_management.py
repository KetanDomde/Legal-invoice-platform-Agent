from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.logger_config import request_id_ctx
from app.models import (
    Alert,
    AuditLog,
    Budget,
    BudgetAdjustment,
    BudgetLedger,
    Firm,
    Invoice,
    Matter,
    User,
)
from app.models.entities import DEFAULT_BUDGET_AMOUNT, DEFAULT_THRESHOLD_PCT


APPROVED_ENTRY_TYPE = "invoice_approved"


def normalize(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().split())


def _request_id() -> str:
    """Return a real trace id for every audit event.

    The normal FastAPI middleware supplies the request id.  The UUID fallback is
    intentionally here as a safety net for service calls made outside a normal
    HTTP request (tests, scripts, background jobs).
    """
    try:
        value = request_id_ctx.get()
    except Exception:
        value = None

    if not value or str(value).strip().lower() in {"n/a", "none", "null"}:
        value = str(uuid.uuid4())
        try:
            request_id_ctx.set(value)
        except Exception:
            pass
    return str(value)


def _audit(
    db: Session,
    action: str,
    *,
    user_id: int = -1,
    invoice_id: int | None = None,
    firm_id: int | None = None,
    matter_id: int | None = None,
    budget_id: int | None = None,
    notes: str | None = None,
    previous_value: str | None = None,
    adjustment_amount: str | None = None,
    new_value: str | None = None,
    reason: str | None = None,
    confirmed: bool | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            invoice_id=invoice_id,
            action=action,
            notes=notes,
            request_id=_request_id(),
            firm_id=firm_id,
            matter_id=matter_id,
            budget_id=budget_id,
            previous_value=previous_value,
            adjustment_amount=adjustment_amount,
            new_value=new_value,
            reason=reason,
            confirmed=confirmed,
        )
    )


def resolve_or_create_from_invoice(
    db: Session,
    *,
    firm_name: str | None,
    firm_address: str | None,
    matter_no: str,
    matter_name: str | None,
    user_id: int = -1,
):
    matter_no = (matter_no or "").strip()
    if not matter_no:
        raise ValueError("A matter identifier is required to resolve the budget.")

    display_firm = (firm_name or "Unassigned Firm (Auto)").strip() or "Unassigned Firm (Auto)"
    display_address = (firm_address or "").strip() or None
    normalized_name = normalize(display_firm)
    normalized_address = normalize(display_address)

    firm = (
        db.query(Firm)
        .filter(
            Firm.normalized_name == normalized_name,
            Firm.normalized_address == normalized_address,
        )
        .first()
    )
    if firm is None:
        firm = Firm(
            name=display_firm,
            address=display_address,
            normalized_name=normalized_name,
            normalized_address=normalized_address,
            status="active",
        )
        db.add(firm)
        db.flush()
        _audit(
            db,
            "FIRM_AUTO_CREATED",
            user_id=user_id,
            firm_id=firm.firm_id,
            notes=f"Firm auto-created from invoice: {firm.name}",
        )

    matter = (
        db.query(Matter)
        .filter(Matter.firm_id == firm.firm_id, Matter.matter_no == matter_no)
        .first()
    )
    created_matter = False
    if matter is None:
        matter = Matter(
            firm_id=firm.firm_id,
            matter_no=matter_no,
            name=(matter_name or f"Auto-created matter ({matter_no})").strip(),
            owner="Unassigned",
            status="open",
        )
        db.add(matter)
        db.flush()
        created_matter = True
        _audit(
            db,
            "MATTER_AUTO_CREATED",
            user_id=user_id,
            firm_id=firm.firm_id,
            matter_id=matter.matter_id,
            notes=f"Matter {matter_no} auto-created from invoice.",
        )
    elif matter_name and normalize(matter.name) != normalize(matter_name):
        _audit(
            db,
            "MATTER_NAME_MISMATCH_DETECTED",
            user_id=user_id,
            firm_id=firm.firm_id,
            matter_id=matter.matter_id,
            notes=(
                f"Existing name: {matter.name}; extracted name: {matter_name}. "
                "Matter ID remained authoritative."
            ),
        )

    budget = db.query(Budget).filter(Budget.matter_id == matter.matter_id).first()
    if budget is None:
        budget = Budget(
            matter_id=matter.matter_id,
            allocated_amt=DEFAULT_BUDGET_AMOUNT,
            threshold_pct=DEFAULT_THRESHOLD_PCT,
        )
        db.add(budget)
        db.flush()
        _audit(
            db,
            "BUDGET_AUTO_CREATED",
            user_id=user_id,
            firm_id=firm.firm_id,
            matter_id=matter.matter_id,
            budget_id=budget.budget_id,
            notes=(
                f"Default budget ${DEFAULT_BUDGET_AMOUNT:,.2f} created with "
                f"{DEFAULT_THRESHOLD_PCT:.0f}% threshold."
            ),
        )

    return firm, matter, budget, created_matter


def budget_usage(db: Session, budget: Budget) -> float:
    return float(
        db.query(func.coalesce(func.sum(BudgetLedger.amount), 0))
        .filter(
            BudgetLedger.budget_id == budget.budget_id,
            BudgetLedger.entry_type == APPROVED_ENTRY_TYPE,
        )
        .scalar()
        or 0
    )


def _intake_status(allocated: float, projected: float, threshold_pct: float) -> str:
    if projected > allocated:
        return "over_budget"
    pct = (projected / allocated * 100) if allocated else 0.0
    if pct >= threshold_pct:
        return "threshold_reached"
    return "within_budget"


def _budget_alert_message(invoice: Invoice, budget: Budget, status: str, remaining: float, pct: float) -> str:
    """Build a human-readable, actionable alert with firm, matter and invoice identity."""
    firm_name = invoice.firm.name if getattr(invoice, "firm", None) else f"Firm #{invoice.firm_id}"
    matter_no = invoice.matter.matter_no if getattr(invoice, "matter", None) else str(invoice.matter_id)
    matter_name = invoice.matter.name if getattr(invoice, "matter", None) else "Unknown matter"
    invoice_no = invoice.invoice_no or f"#{invoice.invoice_id}"
    prefix = f"Firm: {firm_name} | Matter: {matter_no} — {matter_name} | Invoice: {invoice_no}."
    if status == "over_budget":
        return f"{prefix} Invoice exceeds the available budget by ${abs(remaining):,.2f}. Projected utilization: {pct:.1f}%."
    return f"{prefix} Invoice reaches the configured budget threshold. Projected utilization: {pct:.1f}% (threshold {float(budget.threshold_pct):.1f}%)."


def apply_intake_snapshot(db: Session, invoice: Invoice, budget: Budget, user_id: int = -1):
    """Persist immutable intake numbers and create invoice-specific budget alerts.

    Threshold is informational only. Over-budget is the only budget blocker.
    """
    used = budget_usage(db, budget)
    allocated = float(budget.allocated_amt)
    amount = float(invoice.total_amount)
    projected = used + amount
    remaining = allocated - projected
    pct = (projected / allocated * 100) if allocated else 0.0
    status = _intake_status(allocated, projected, float(budget.threshold_pct))

    invoice.budget_id_at_intake = budget.budget_id
    invoice.budget_amount_at_intake = allocated
    invoice.budget_used_before_invoice = used
    invoice.budget_projected_after_invoice = projected
    invoice.budget_remaining_after_invoice = remaining
    invoice.budget_projected_pct = pct
    invoice.budget_status_at_intake = status
    invoice.budget_attention_required = status == "over_budget"
    invoice.budget_valid = status != "over_budget"

    if status != "within_budget":
        alert_type = "OVER_BUDGET_DETECTED" if status == "over_budget" else "BUDGET_THRESHOLD_REACHED"
        message = _budget_alert_message(invoice, budget, status, remaining, pct)
        existing = (
            db.query(Alert)
            .filter(
                Alert.budget_id == budget.budget_id,
                Alert.invoice_id == invoice.invoice_id,
                Alert.type == alert_type,
                Alert.is_active.is_(True),
            )
            .first()
        )
        if existing is None:
            db.add(Alert(budget_id=budget.budget_id, invoice_id=invoice.invoice_id, type=alert_type, message=message, is_active=True))
            _audit(db, alert_type, user_id=user_id, invoice_id=invoice.invoice_id, firm_id=invoice.firm_id, matter_id=invoice.matter_id, budget_id=budget.budget_id, notes=message)

    _audit(
        db, "INVOICE_ASSOCIATED_WITH_MATTER", user_id=user_id, invoice_id=invoice.invoice_id,
        firm_id=invoice.firm_id, matter_id=invoice.matter_id, budget_id=budget.budget_id,
        notes=f"Invoice associated with matter {invoice.matter.matter_no if invoice.matter else invoice.matter_id}.",
    )
    return status


def _deactivate_alerts_for_invoice(db: Session, invoice_id: int, types: tuple[str, ...]) -> int:
    rows = (
        db.query(Alert)
        .filter(
            Alert.invoice_id == invoice_id,
            Alert.is_active.is_(True),
            Alert.type.in_(types),
        )
        .all()
    )
    now = datetime.now(timezone.utc)
    for row in rows:
        row.is_active = False
        row.resolved_at = now
    return len(rows)


def _current_invoice_budget_result(db: Session, invoice: Invoice, budget: Budget) -> dict:
    used = budget_usage(db, budget)
    existing_post = (
        db.query(BudgetLedger)
        .filter(
            BudgetLedger.budget_id == budget.budget_id,
            BudgetLedger.invoice_id == invoice.invoice_id,
            BudgetLedger.entry_type == APPROVED_ENTRY_TYPE,
        )
        .first()
    )
    projected = used if existing_post else used + float(invoice.total_amount or 0)
    allocated = float(budget.allocated_amt or 0)
    remaining = allocated - projected
    pct = (projected / allocated * 100) if allocated else 0.0
    status = _intake_status(allocated, projected, float(budget.threshold_pct or 0))
    return {
        "budget_result": status,
        "remaining_after_invoice": remaining,
        "projected_utilization": pct,
        "needs_attention": status == "over_budget",
    }


def reconcile_budget_after_adjustment(db: Session, *, budget: Budget, user: User) -> dict:
    """Reconcile pending invoices after a budget adjustment.

    If the budget was the reason an invoice was pending and the invoice now passes
    validation, approve it automatically. Other validation failures remain pending
    and their exact reasons are preserved for the admin UI.
    """
    pending = (
        db.query(Invoice)
        .filter(Invoice.matter_id == budget.matter_id, Invoice.status == "pending_review")
        .order_by(Invoice.invoice_id.asc())
        .all()
    )
    auto_approved, still_pending = [], []
    resolved_alerts = 0

    from app.services.invoice import validate_invoice, add_audit_log
    from app.workflow.approval_service import auto_approve_invoice

    for invoice in pending:
        before_budget_blocker = bool(invoice.budget_attention_required)
        result = validate_invoice(db=db, invoice=invoice)
        reasons = [r for r in (result.get("reasons") or []) if r]

        invoice.confidence_score = result.get("confidence_score", invoice.confidence_score)
        invoice.budget_valid = bool(result.get("budget_ok"))
        invoice.duplicate_flag = bool(result.get("duplicate"))
        invoice.validation_status = "passed" if result.get("validation_passed") else "failed"
        invoice.validation_message = "; ".join(reasons)
        invoice.budget_attention_required = not bool(result.get("budget_ok"))

        # A budget adjustment resolves old invoice-specific budget alerts. Threshold
        # warnings are historical snapshots, not unresolved blockers, so do not keep
        # stale alerts after reconciliation.
        if result.get("budget_ok"):
            resolved_alerts += _deactivate_alerts_for_invoice(
                db, invoice.invoice_id,
                ("OVER_BUDGET_DETECTED", "budget_overrun", "BUDGET_THRESHOLD_REACHED", "budget_threshold"),
            )

        # Do not depend on result['decision'] here. Reconciliation is after a budget
        # change; validation_passed is the authoritative answer to whether any other
        # blocker remains.
        budget_was_only_blocker = before_budget_blocker and bool(result.get("validation_passed")) and bool(result.get("budget_ok"))
        if budget_was_only_blocker:
            old_status = invoice.status
            invoice.status = "submitted"
            db.flush()
            auto_approve_invoice(db=db, invoice=invoice)
            auto_approved.append({
                "invoice_id": invoice.invoice_id,
                "invoice_no": invoice.invoice_no,
                "reason": "Budget was the only blocker; after the adjustment all validation checks pass.",
            })
            _audit(
                db, "BUDGET_BLOCKER_RESOLVED_AUTO_APPROVED", user_id=user.user_id,
                invoice_id=invoice.invoice_id, firm_id=invoice.firm_id, matter_id=invoice.matter_id,
                budget_id=budget.budget_id,
                notes=f"Budget adjustment removed the only blocker. Invoice changed from '{old_status}' to approved automatically.",
            )
        else:
            invoice.status = "pending_review"
            if result.get("budget_ok") and not before_budget_blocker:
                pending_reason = "Invoice remains pending because of non-budget validation issues. " + "; ".join(reasons)
            elif result.get("budget_ok"):
                pending_reason = "Budget is resolved, but non-budget validation issues remain. " + "; ".join(reasons)
            else:
                pending_reason = "Budget issue still remains. " + "; ".join(reasons)
            still_pending.append({"invoice_id": invoice.invoice_id, "invoice_no": invoice.invoice_no, "reasons": reasons})
            add_audit_log(db=db, action="budget_reconciled_pending_review", user_id=user.user_id, invoice_id=invoice.invoice_id, notes=pending_reason)

    # Resolve stale budget alerts for every invoice in this matter after the new budget
    # is effective. Current utilization remains visible in the UI as a warning.
    all_matter_invoices = db.query(Invoice).filter(Invoice.matter_id == budget.matter_id).all()
    for invoice in all_matter_invoices:
        current = _current_invoice_budget_result(db, invoice, budget)
        if not current["needs_attention"]:
            resolved_alerts += _deactivate_alerts_for_invoice(
                db, invoice.invoice_id,
                ("OVER_BUDGET_DETECTED", "budget_overrun", "BUDGET_THRESHOLD_REACHED", "budget_threshold"),
            )

    return {"auto_approved": auto_approved, "still_pending": still_pending, "resolved_alerts": resolved_alerts}


def adjust_budget(
    db: Session,
    *,
    budget: Budget,
    amount: float,
    reason: str,
    confirmed: bool,
    user: User,
    invoice_id: int | None = None,
):
    if not confirmed:
        raise ValueError("Budget adjustment must be explicitly confirmed.")
    if not reason or not reason.strip():
        raise ValueError("A reason is required for every budget adjustment.")
    if amount == 0:
        raise ValueError("Adjustment amount cannot be zero.")

    previous = float(budget.allocated_amt)
    new = previous + float(amount)
    if new <= 0:
        raise ValueError("Budget cannot be zero or negative after adjustment.")

    adjustment = BudgetAdjustment(
        budget_id=budget.budget_id,
        invoice_id=invoice_id,
        adjusted_by_user_id=user.user_id,
        previous_amount=previous,
        adjustment_amount=float(amount),
        new_amount=new,
        adjustment_type="increase" if amount > 0 else "decrease",
        reason=reason.strip(),
        confirmed=True,
    )
    budget.allocated_amt = new
    db.add(adjustment)
    db.flush()

    matter = db.get(Matter, budget.matter_id)
    _audit(
        db,
        "BUDGET_INCREASED" if amount > 0 else "BUDGET_DECREASED",
        user_id=user.user_id,
        invoice_id=invoice_id,
        firm_id=matter.firm_id if matter else None,
        matter_id=budget.matter_id,
        budget_id=budget.budget_id,
        previous_value=f"{previous:.2f}",
        adjustment_amount=f"{amount:+.2f}",
        new_value=f"{new:.2f}",
        reason=reason.strip(),
        confirmed=True,
        notes=(
            f"Budget adjustment confirmed by admin for "
            f"{matter.matter_no if matter and getattr(matter, 'matter_no', None) else 'the selected matter'}"
            + (
                f"; related invoice {db.get(Invoice, invoice_id).invoice_no or invoice_id}."
                if invoice_id is not None and db.get(Invoice, invoice_id) is not None
                else "; no specific invoice was selected."
            )
        ),
    )
    return adjustment

def budget_hierarchy(db: Session, firm_id: int | None = None):
    """
    Return the Budgets & Alerts hierarchy.

    A firm can be automatically expanded by the frontend when it contains:

    1. The newest invoice in the accessible data.
    2. A matter currently over budget.
    3. A matter currently at or above its configured threshold.
    4. One or more active alerts.

    Invoice IDs are used to identify the newest invoice because the current
    Invoice model does not have a created_at column.
    """

    q = (
        db.query(Firm)
        .options(
            joinedload(Firm.matters).joinedload(Matter.budget),
            joinedload(Firm.matters).joinedload(Matter.invoices),
        )
        .order_by(Firm.name)
    )

    if firm_id is not None:
        q = q.filter(Firm.firm_id == firm_id)

    firms = q.all()

    # -----------------------------------------------------------------------
    # Determine the newest accessible invoice.
    #
    # The current Invoice entity has no created_at column, therefore the
    # highest auto-increment invoice_id is the reliable "most recently added"
    # indicator available without changing the database schema.
    # -----------------------------------------------------------------------
    newest_invoice_id = None

    for firm in firms:
        for matter in firm.matters:
            for invoice in matter.invoices:
                if (
                    newest_invoice_id is None
                    or invoice.invoice_id > newest_invoice_id
                ):
                    newest_invoice_id = invoice.invoice_id

    result = []

    for firm in firms:
        matters = []

        for matter in firm.matters:
            if not matter.budget:
                continue

            budget = matter.budget
            used = budget_usage(db, budget)
            allocated = float(budget.allocated_amt or 0)

            pct = (
                used / allocated * 100
                if allocated > 0
                else 0.0
            )

            threshold_pct = float(
                budget.threshold_pct or 0
            )

            invoices = []

            for invoice in sorted(
                matter.invoices,
                key=lambda x: x.invoice_id,
                reverse=True,
            ):
                current = _current_invoice_budget_result(
                    db,
                    invoice,
                    budget,
                )

                invoices.append(
                    {
                        "invoice_id": invoice.invoice_id,
                        "invoice_no": invoice.invoice_no,
                        "amount": float(
                            invoice.total_amount or 0
                        ),
                        "status": invoice.status,

                        "budget_result": current[
                            "budget_result"
                        ],
                        "remaining_after_invoice": current[
                            "remaining_after_invoice"
                        ],
                        "projected_utilization": current.get(
                            "projected_utilization"
                        ),
                        "needs_attention": current[
                            "needs_attention"
                        ],

                        "intake_budget_result": (
                            invoice.budget_status_at_intake
                        ),
                        "intake_remaining_after_invoice": (
                            float(
                                invoice.budget_remaining_after_invoice
                            )
                            if invoice.budget_remaining_after_invoice
                            is not None
                            else None
                        ),

                        "validation_message": (
                            invoice.validation_message
                        ),

                        # True only for the newest invoice in the currently
                        # accessible dataset.
                        "is_newest_invoice": (
                            invoice.invoice_id
                            == newest_invoice_id
                        ),
                    }
                )

            active_alert_count = (
                db.query(Alert)
                .filter(
                    Alert.budget_id == budget.budget_id,
                    Alert.is_active.is_(True),
                )
                .count()
            )

            threshold_reached = (
                pct >= threshold_pct
            )

            over_budget = (
                used > allocated
            )

            matters.append(
                {
                    "matter_id": matter.matter_id,
                    "matter_no": matter.matter_no,
                    "matter_name": matter.name,

                    "budget_id": budget.budget_id,

                    "allocated": allocated,
                    "utilized": used,
                    "remaining": allocated - used,
                    "pct_used": pct,

                    "threshold_pct": threshold_pct,
                    "threshold_reached": threshold_reached,
                    "over_budget": over_budget,

                    "active_alert_count": active_alert_count,
                    "invoices": invoices,

                    # Used directly by the frontend to determine whether the
                    # parent firm deserves automatic attention/expansion.
                    "requires_attention": (
                        over_budget
                        or threshold_reached
                        or active_alert_count > 0
                        or any(
                            inv["is_newest_invoice"]
                            for inv in invoices
                        )
                    ),
                }
            )

        if matters:
            firm_requires_attention = any(
                matter["requires_attention"]
                for matter in matters
            )

            result.append(
                {
                    "firm_id": firm.firm_id,
                    "firm_name": firm.name,
                    "firm_address": firm.address,

                    "matters": matters,

                    "requires_attention": (
                        firm_requires_attention
                    ),
                }
            )

    return result