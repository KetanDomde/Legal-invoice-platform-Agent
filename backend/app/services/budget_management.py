from __future__ import annotations

from datetime import datetime, timezone

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


def _request_id() -> str | None:
    try:
        return request_id_ctx.get()
    except Exception:
        return None


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


def apply_intake_snapshot(db: Session, invoice: Invoice, budget: Budget, user_id: int = -1):
    """Persist immutable intake numbers and create invoice-specific alerts.

    A threshold warning is informational; only an actual over-budget condition is
    a budget blocker. This prevents threshold-only invoices from being forced to
    human review.
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
        message = (
            f"Invoice {invoice.invoice_no or invoice.invoice_id} would exceed budget by ${abs(remaining):,.2f}."
            if status == "over_budget"
            else (
                f"Invoice {invoice.invoice_no or invoice.invoice_id} would take budget utilization "
                f"to {pct:.1f}% (threshold {float(budget.threshold_pct):.1f}%)."
            )
        )
        db.add(
            Alert(
                budget_id=budget.budget_id,
                invoice_id=invoice.invoice_id,
                type=alert_type,
                message=message,
                is_active=True,
            )
        )
        _audit(
            db,
            alert_type,
            user_id=user_id,
            invoice_id=invoice.invoice_id,
            firm_id=invoice.firm_id,
            matter_id=invoice.matter_id,
            budget_id=budget.budget_id,
            notes=message,
        )

    _audit(
        db,
        "INVOICE_ASSOCIATED_WITH_MATTER",
        user_id=user_id,
        invoice_id=invoice.invoice_id,
        firm_id=invoice.firm_id,
        matter_id=invoice.matter_id,
        budget_id=budget.budget_id,
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
    """Return the budget result for one invoice using the correct time context.

    Pending invoices are projected against the current approved spend because
    they have not been posted to the ledger yet. Approved invoices use their
    immutable intake snapshot when available, so older rows do not all change
    to the latest budget position after a later adjustment.
    """
    existing_post = (
        db.query(BudgetLedger)
        .filter(
            BudgetLedger.budget_id == budget.budget_id,
            BudgetLedger.invoice_id == invoice.invoice_id,
            BudgetLedger.entry_type == APPROVED_ENTRY_TYPE,
        )
        .first()
    )

    allocated = float(budget.allocated_amt or 0)

    # A pending invoice is a projection against today's approved spend.
    if invoice.status == "pending_review" and existing_post is None:
        used = budget_usage(db, budget)
        projected = used + float(invoice.total_amount or 0)
        remaining = allocated - projected
        pct = (projected / allocated * 100) if allocated else 0.0
        status = _intake_status(allocated, projected, float(budget.threshold_pct or 0))
        return {
            "budget_result": status,
            "remaining_after_invoice": remaining,
            "projected_utilization": pct,
            "needs_attention": status == "over_budget",
        }

    # Approved invoices should retain their historical intake result.
    if existing_post is not None and invoice.budget_status_at_intake:
        pct = (
            float(invoice.budget_projected_pct)
            if invoice.budget_projected_pct is not None
            else 0.0
        )
        remaining = (
            float(invoice.budget_remaining_after_invoice)
            if invoice.budget_remaining_after_invoice is not None
            else allocated - float(invoice.budget_projected_after_invoice or 0)
        )
        status = invoice.budget_status_at_intake
        return {
            "budget_result": status,
            "remaining_after_invoice": remaining,
            "projected_utilization": pct,
            "needs_attention": status == "over_budget",
        }

    # Backward-compatible fallback for older invoices without snapshots.
    used = budget_usage(db, budget)
    projected = used if existing_post else used + float(invoice.total_amount or 0)
    remaining = allocated - projected
    pct = (projected / allocated * 100) if allocated else 0.0
    status = _intake_status(allocated, projected, float(budget.threshold_pct or 0))
    return {
        "budget_result": status,
        "remaining_after_invoice": remaining,
        "projected_utilization": pct,
        "needs_attention": status == "over_budget",
    }


def _ensure_current_budget_alert(
    db: Session,
    *,
    budget: Budget,
    matter: Matter,
    alert_type: str,
    invoice_id: int | None = None,
    message: str,
    user_id: int = -1,
) -> bool:
    """Ensure the current budget state has one active alert of ``alert_type``.

    Budget alerts are state-based, not only intake-event-based.  A budget
    adjustment can change an invoice from over-budget to threshold-only (or
    leave the matter over budget), so reconciliation must restore the current
    alert after resolving stale invoice-specific alerts.
    """
    existing = (
        db.query(Alert)
        .filter(
            Alert.budget_id == budget.budget_id,
            Alert.type == alert_type,
            Alert.is_active.is_(True),
        )
        .order_by(Alert.alert_id.desc())
        .first()
    )

    if existing is not None:
        existing.message = message
        # The alert represents the current state. Clear stale invoice links when
        # there is no current pending invoice, and replace them when there is one.
        existing.invoice_id = invoice_id
        return False

    alert = Alert(
        budget_id=budget.budget_id,
        invoice_id=invoice_id,
        type=alert_type,
        message=message,
        is_active=True,
    )
    db.add(alert)
    db.flush()

    _audit(
        db,
        alert_type,
        user_id=user_id,
        invoice_id=invoice_id,
        firm_id=matter.firm_id,
        matter_id=matter.matter_id,
        budget_id=budget.budget_id,
        notes=message,
    )
    return True


def _deactivate_budget_alert_type(db: Session, budget_id: int, alert_type: str) -> int:
    """Deactivate all active alerts of one type for a budget."""
    rows = (
        db.query(Alert)
        .filter(
            Alert.budget_id == budget_id,
            Alert.type == alert_type,
            Alert.is_active.is_(True),
        )
        .all()
    )
    now = datetime.now(timezone.utc)
    for row in rows:
        row.is_active = False
        row.resolved_at = now
    return len(rows)


def _sync_budget_state_alert(db: Session, *, budget: Budget, matter: Matter, user_id: int) -> tuple[int, int]:
    """Synchronize the single canonical active alert for a budget.

    Rules:
      1. A pending invoice is projected against current approved spend.
      2. If that projection exceeds 100%, the active alert is OVER_BUDGET_DETECTED.
      3. Otherwise, if current/projection utilization is >= threshold, the active
         alert is BUDGET_THRESHOLD_REACHED.
      4. Below threshold, no budget alert remains active.

    This is the source of truth used by Home, Matter & Budget, and Budgets &
    Alerts. It deliberately does not change the approved ledger merely because
    an invoice is pending.
    """
    used = budget_usage(db, budget)
    allocated = float(budget.allocated_amt or 0)
    threshold = float(budget.threshold_pct or 0)

    # Prefer the newest pending invoice because it is the current unresolved
    # budget decision the user needs to see. If none is pending, use the latest
    # approved ledger invoice only as the contextual invoice reference.
    pending_invoice = (
        db.query(Invoice)
        .filter(
            Invoice.matter_id == budget.matter_id,
            Invoice.status == "pending_review",
        )
        .order_by(Invoice.invoice_id.desc())
        .first()
    )

    if pending_invoice is not None:
        invoice_id = pending_invoice.invoice_id
        projected = used + float(pending_invoice.total_amount or 0)
        projected_pct = (projected / allocated * 100) if allocated > 0 else 0.0
        projected_remaining = allocated - projected
    else:
        invoice_id = (
            db.query(BudgetLedger.invoice_id)
            .filter(
                BudgetLedger.budget_id == budget.budget_id,
                BudgetLedger.entry_type == APPROVED_ENTRY_TYPE,
                BudgetLedger.invoice_id.isnot(None),
            )
            .order_by(BudgetLedger.ledger_id.desc())
            .first()
        )
        invoice_id = invoice_id[0] if invoice_id else None
        projected = used
        projected_pct = (used / allocated * 100) if allocated > 0 else 0.0
        projected_remaining = allocated - used

    created = 0
    resolved = 0

    if projected > allocated:
        if pending_invoice is not None:
            message = (
                f"Firm: {matter.firm.name if matter.firm else '—'} | "
                f"Matter: {matter.matter_no or '—'} — {matter.name} | "
                f"Invoice: {pending_invoice.invoice_no or f'#{pending_invoice.invoice_id}'}. "
                f"Invoice is pending review and would exceed the available budget "
                f"by ${abs(projected_remaining):,.2f}. "
                f"Projected spend is ${projected:,.2f} against ${allocated:,.2f}; "
                f"projected utilization is {projected_pct:.1f}%."
            )
        else:
            message = (
                f"Firm: {matter.firm.name if matter.firm else '—'} | "
                f"Matter: {matter.matter_no or '—'} — {matter.name}. "
                f"Budget is over the effective limit. Approved spend is "
                f"${used:,.2f} against ${allocated:,.2f}; utilization is {projected_pct:.1f}%."
            )

        created += int(
            _ensure_current_budget_alert(
                db,
                budget=budget,
                matter=matter,
                alert_type="OVER_BUDGET_DETECTED",
                invoice_id=invoice_id,
                message=message,
                user_id=user_id,
            )
        )
        resolved += _deactivate_budget_alert_type(db, budget.budget_id, "BUDGET_THRESHOLD_REACHED")
        resolved += _deactivate_budget_alert_type(db, budget.budget_id, "budget_threshold")
        resolved += _deactivate_budget_alert_type(db, budget.budget_id, "budget_overrun")

    elif projected_pct >= threshold:
        if pending_invoice is not None:
            message = (
                f"Firm: {matter.firm.name if matter.firm else '—'} | "
                f"Matter: {matter.matter_no or '—'} — {matter.name} | "
                f"Invoice: {pending_invoice.invoice_no or f'#{pending_invoice.invoice_id}'}. "
                f"Invoice is pending review and would take budget utilization to "
                f"{projected_pct:.1f}% (threshold {threshold:.1f}%)."
            )
        else:
            message = (
                f"Firm: {matter.firm.name if matter.firm else '—'} | "
                f"Matter: {matter.matter_no or '—'} — {matter.name}. "
                f"Budget threshold reached. Current utilization is {projected_pct:.1f}% "
                f"(threshold {threshold:.1f}%)."
            )

        created += int(
            _ensure_current_budget_alert(
                db,
                budget=budget,
                matter=matter,
                alert_type="BUDGET_THRESHOLD_REACHED",
                invoice_id=invoice_id,
                message=message,
                user_id=user_id,
            )
        )
        resolved += _deactivate_budget_alert_type(db, budget.budget_id, "OVER_BUDGET_DETECTED")
        resolved += _deactivate_budget_alert_type(db, budget.budget_id, "budget_overrun")
        resolved += _deactivate_budget_alert_type(db, budget.budget_id, "budget_threshold")
    else:
        for alert_type in (
            "OVER_BUDGET_DETECTED",
            "budget_overrun",
            "BUDGET_THRESHOLD_REACHED",
            "budget_threshold",
        ):
            resolved += _deactivate_budget_alert_type(db, budget.budget_id, alert_type)

    return created, resolved


def reconcile_budget_after_adjustment(db: Session, *, budget: Budget, user: User) -> dict:
    """Re-evaluate pending invoices after an admin changes a budget.

    Only invoices whose budget blocker disappeared are candidates for automatic
    approval. The normal validation function is reused, so low confidence,
    duplicate, and other validation blockers still keep the invoice pending.
    """
    matter = db.get(Matter, budget.matter_id)
    pending = (
        db.query(Invoice)
        .filter(
            Invoice.matter_id == budget.matter_id,
            Invoice.status == "pending_review",
        )
        .order_by(Invoice.invoice_id.asc())
        .all()
    )

    auto_approved: list[dict] = []
    still_pending: list[dict] = []
    resolved_alerts = 0

    # Imported lazily to avoid service import cycles.
    from app.services.invoice import validate_invoice, add_audit_log
    from app.workflow.approval_service import auto_approve_invoice

    for invoice in pending:
        before_budget_blocker = bool(invoice.budget_attention_required)
        result = validate_invoice(db=db, invoice=invoice)

        invoice.confidence_score = result["confidence_score"]
        invoice.budget_valid = result["budget_ok"]
        invoice.duplicate_flag = result["duplicate"]
        invoice.validation_status = "passed" if result["validation_passed"] else "failed"
        invoice.validation_message = "; ".join(result["reasons"])
        invoice.budget_attention_required = not result["budget_ok"]

        if result["budget_ok"]:
            resolved_alerts += _deactivate_alerts_for_invoice(
                db,
                invoice.invoice_id,
                ("OVER_BUDGET_DETECTED", "budget_overrun"),
            )
            current = _current_invoice_budget_result(db, invoice, budget)
            if current["budget_result"] == "within_budget":
                resolved_alerts += _deactivate_alerts_for_invoice(
                    db,
                    invoice.invoice_id,
                    ("BUDGET_THRESHOLD_REACHED", "budget_threshold"),
                )

        if result["decision"] == "auto_approved" and before_budget_blocker:
            old_status = invoice.status
            invoice.status = "submitted"
            db.flush()
            auto_approve_invoice(db=db, invoice=invoice)
            auto_approved.append(
                {
                    "invoice_id": invoice.invoice_id,
                    "invoice_no": invoice.invoice_no,
                    "reason": "Budget was the only remaining blocker and the invoice now passes validation.",
                }
            )
            _audit(
                db,
                "BUDGET_BLOCKER_RESOLVED_AUTO_APPROVED",
                user_id=user.user_id,
                invoice_id=invoice.invoice_id,
                firm_id=invoice.firm_id,
                matter_id=invoice.matter_id,
                budget_id=budget.budget_id,
                notes=(
                    f"Budget adjustment removed the budget blocker. Invoice changed from "
                    f"'{old_status}' to approved automatically."
                ),
            )
        else:
            invoice.status = "pending_review"
            still_pending.append(
                {
                    "invoice_id": invoice.invoice_id,
                    "invoice_no": invoice.invoice_no,
                    "reasons": result["reasons"],
                }
            )
            add_audit_log(
                db=db,
                action="budget_reconciled_pending_review",
                user_id=user.user_id,
                invoice_id=invoice.invoice_id,
                notes=(
                    "Budget changed, but invoice remains pending review. "
                    + "; ".join(result["reasons"])
                ),
            )

    # Reconcile the final ledger-backed budget state.
    #
    # IMPORTANT: resolving the invoice's old budget blocker must NOT mean that
    # all alerts disappear.  If the new budget is still at/above the configured
    # threshold, a threshold warning must remain active; if it is still above
    # 100%, an over-budget alert must remain active.
    created_alerts, state_resolved_alerts = _sync_budget_state_alert(
        db,
        budget=budget,
        matter=matter,
        user_id=user.user_id,
    )
    resolved_alerts += state_resolved_alerts

    return {
        "auto_approved": auto_approved,
        "still_pending": still_pending,
        "resolved_alerts": resolved_alerts,
        "created_alerts": created_alerts,
    }


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
        notes="Budget adjustment confirmed by admin.",
    )
    return adjustment


def budget_hierarchy(db: Session, firm_id: int | None = None):
    """
    Return the Firm -> Matter -> Budget -> Invoice hierarchy used by
    Home, Matter & Budget, and Budgets & Alerts.

    Budget semantics:
    - `utilized`, `remaining`, and `pct_used` represent the CURRENT
      approved ledger-backed spend.
    - `projected_*` fields include the newest pending-review invoice,
      when one exists.
    - The approved BudgetLedger is never modified merely because an
      invoice is pending review.

    This keeps approved financial utilization separate from projected
    utilization while exposing both values to the UI.
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

    # Synchronize persisted budget alerts before returning the hierarchy.
    # This ensures that a pending invoice which exceeds the budget has
    # an active budget alert.
    firms = q.all()

    for firm in firms:
        for matter in firm.matters:
            if not matter.budget:
                continue

            _sync_budget_state_alert(
                db,
                budget=matter.budget,
                matter=matter,
                user_id=-1,
            )

    db.commit()

    result = []

    for firm in firms:
        matters = []

        for matter in firm.matters:
            if not matter.budget:
                continue

            budget = matter.budget

            # ---------------------------------------------------------
            # Current approved budget state
            # ---------------------------------------------------------
            used = budget_usage(db, budget)
            allocated = float(budget.allocated_amt or 0)
            threshold_pct = float(budget.threshold_pct or 0)

            pct = (
                (used / allocated) * 100
                if allocated > 0
                else 0.0
            )

            remaining = allocated - used

            # ---------------------------------------------------------
            # Pending-review projection
            # ---------------------------------------------------------
            #
            # Only the newest pending invoice is projected here.
            # This matches _sync_budget_state_alert(), which treats the
            # newest unresolved invoice as the current budget decision.
            #
            pending_invoice = (
                db.query(Invoice)
                .filter(
                    Invoice.matter_id == matter.matter_id,
                    Invoice.status == "pending_review",
                )
                .order_by(Invoice.invoice_id.desc())
                .first()
            )

            if pending_invoice is not None:
                pending_amount = float(
                    pending_invoice.total_amount or 0
                )

                projected_used = used + pending_amount

                projected_pct = (
                    (projected_used / allocated) * 100
                    if allocated > 0
                    else 0.0
                )

                projected_remaining = (
                    allocated - projected_used
                )

                projected_status = _intake_status(
                    allocated,
                    projected_used,
                    threshold_pct,
                )

                projected_threshold_reached = (
                    projected_pct >= threshold_pct
                )

                projected_over_budget = (
                    projected_used > allocated
                )

                pending_invoice_id = pending_invoice.invoice_id
            else:
                # No pending invoice means current and projected
                # utilization are identical.
                projected_used = used
                projected_pct = pct
                projected_remaining = remaining

                projected_status = _intake_status(
                    allocated,
                    projected_used,
                    threshold_pct,
                )

                projected_threshold_reached = (
                    projected_pct >= threshold_pct
                )

                projected_over_budget = (
                    projected_used > allocated
                )

                pending_invoice_id = None

            # ---------------------------------------------------------
            # Invoice details
            # ---------------------------------------------------------
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
                        "amount": float(invoice.total_amount or 0),
                        "status": invoice.status,

                        # Current invoice-specific budget decision
                        "budget_result": current["budget_result"],
                        "remaining_after_invoice": (
                            current["remaining_after_invoice"]
                        ),
                        "projected_utilization": (
                            current["projected_utilization"]
                        ),
                        "needs_attention": (
                            current["needs_attention"]
                        ),

                        # Immutable intake snapshot
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

                        "intake_projected_utilization": (
                            float(invoice.budget_projected_pct)
                            if invoice.budget_projected_pct
                            is not None
                            else None
                        ),

                        "intake_budget_amount": (
                            float(invoice.budget_amount_at_intake)
                            if invoice.budget_amount_at_intake
                            is not None
                            else None
                        ),

                        "intake_used_before_invoice": (
                            float(invoice.budget_used_before_invoice)
                            if invoice.budget_used_before_invoice
                            is not None
                            else None
                        ),

                        "intake_projected_after_invoice": (
                            float(
                                invoice.budget_projected_after_invoice
                            )
                            if invoice.budget_projected_after_invoice
                            is not None
                            else None
                        ),

                        "validation_message": (
                            invoice.validation_message
                        ),
                    }
                )

            # ---------------------------------------------------------
            # Active alerts
            # ---------------------------------------------------------
            active_alert_count = (
                db.query(Alert)
                .filter(
                    Alert.budget_id == budget.budget_id,
                    Alert.is_active.is_(True),
                )
                .count()
            )

            # ---------------------------------------------------------
            # Matter-level budget response
            # ---------------------------------------------------------
            matters.append(
                {
                    "matter_id": matter.matter_id,
                    "matter_no": matter.matter_no,
                    "matter_name": matter.name,

                    "budget_id": budget.budget_id,

                    # Current / approved ledger state
                    "allocated": allocated,
                    "utilized": used,
                    "remaining": remaining,
                    "pct_used": pct,

                    # Existing threshold information
                    "threshold_pct": threshold_pct,
                    "threshold_reached": (
                        pct >= threshold_pct
                    ),
                    "over_budget": (
                        pct > 100
                    ),

                    # -------------------------------------------------
                    # NEW: projected state including pending invoice
                    # -------------------------------------------------
                    "projected_utilized": projected_used,
                    "projected_remaining": projected_remaining,
                    "projected_pct_used": projected_pct,
                    "projected_threshold_reached": (
                        projected_threshold_reached
                    ),
                    "projected_over_budget": (
                        projected_over_budget
                    ),
                    "projected_status": projected_status,

                    # Helpful context for the UI
                    "pending_invoice_id": pending_invoice_id,
                    "pending_invoice_amount": (
                        float(pending_invoice.total_amount or 0)
                        if pending_invoice is not None
                        else 0.0
                    ),

                    "active_alert_count": active_alert_count,

                    "invoices": invoices,
                }
            )

        if matters:
            result.append(
                {
                    "firm_id": firm.firm_id,
                    "firm_name": firm.name,
                    "firm_address": firm.address,
                    "matters": matters,
                }
            )

    return result

# def budget_hierarchy(db: Session, firm_id: int | None = None):
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

    # Keep persisted alerts synchronized with the current ledger-backed budget state
    # before returning the hierarchy. This also repairs older databases where an
    # invoice-specific alert was dismissed during budget reconciliation but the
    # matter remained above its configured threshold.
    firms = q.all()
    for firm in firms:
        for matter in firm.matters:
            if not matter.budget:
                continue
            _sync_budget_state_alert(
                db,
                budget=matter.budget,
                matter=matter,
                user_id=-1,
            )
    db.commit()

    result = []
    for firm in firms:
        matters = []
        for matter in firm.matters:
            if not matter.budget:
                continue
            budget = matter.budget
            used = budget_usage(db, budget)
            allocated = float(budget.allocated_amt or 0)
            pct = (used / allocated * 100) if allocated else 0.0
            invoices = []
            for invoice in sorted(matter.invoices, key=lambda x: x.invoice_id, reverse=True):
                current = _current_invoice_budget_result(db, invoice, budget)
                invoices.append(
                    {
                        "invoice_id": invoice.invoice_id,
                        "invoice_no": invoice.invoice_no,
                        "amount": float(invoice.total_amount or 0),
                        "status": invoice.status,
                        "budget_result": current["budget_result"],
                        "remaining_after_invoice": current["remaining_after_invoice"],
                        "projected_utilization": current["projected_utilization"],
                        "needs_attention": current["needs_attention"],
                        "intake_budget_result": invoice.budget_status_at_intake,
                        "intake_remaining_after_invoice": (
                            float(invoice.budget_remaining_after_invoice)
                            if invoice.budget_remaining_after_invoice is not None
                            else None
                        ),
                        "validation_message": invoice.validation_message,
                    }
                )

            active_alert_count = (
                db.query(Alert)
                .filter(Alert.budget_id == budget.budget_id, Alert.is_active.is_(True))
                .count()
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
                    "threshold_pct": float(budget.threshold_pct or 0),
                    "threshold_reached": pct >= float(budget.threshold_pct or 0),
                    "over_budget": pct > 100,
                    "active_alert_count": active_alert_count,
                    "invoices": invoices,
                }
            )
        if matters:
            result.append(
                {
                    "firm_id": firm.firm_id,
                    "firm_name": firm.name,
                    "firm_address": firm.address,
                    "matters": matters,
                }
            )
    return result