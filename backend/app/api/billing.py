from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.security import ADMIN, EDITOR, get_current_user, require_role
from app.database.database import get_db
from app.models import Alert, Budget, BudgetAdjustment, BudgetLedger, Firm, Invoice, LineItem, Matter, User
from app.schemas.billing import (
    AlertCreate,
    AlertRead,
    BudgetCreate,
    BudgetLedgerCreate,
    BudgetLedgerRead,
    BudgetRead,
    BudgetUpdate,
    BudgetAdjustmentCreate,
    FirmCreate,
    FirmRead,
    FirmUpdate,
    InvoiceCreate,
    InvoiceRead,
    InvoiceUpdate,
    LineItemCreate,
    LineItemRead,
    LineItemUpdate,
    MatterCreate,
    MatterRead,
    MatterUpdate,
)
from app.services.budget import (
    get_all_budget_summaries,
    get_budget_summary,
)
from app.services.budget_management import budget_hierarchy, adjust_budget, reconcile_budget_after_adjustment

router = APIRouter(tags=["Billing"])


def _ensure_firm_access(current_user: User, firm_id: int) -> None:
    if current_user.firm_id is not None and current_user.firm_id != firm_id:
        raise HTTPException(status_code=403, detail="Permission denied")


def _get_firm_or_404(db: Session, firm_id: int) -> Firm:
    firm = db.get(Firm, firm_id)
    if firm is None:
        raise HTTPException(status_code=404, detail="Firm not found")
    return firm


def _get_matter_or_404(db: Session, matter_id: int) -> Matter:
    matter = db.get(Matter, matter_id)
    if matter is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    return matter


def _get_invoice_or_404(db: Session, invoice_id: int) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


# ---------------------------------------------------------------------------
# Firms
# ---------------------------------------------------------------------------

@router.post("/firms", response_model=FirmRead, status_code=status.HTTP_201_CREATED)
def create_firm(
    request: FirmCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    if current_user.firm_id is not None:
        raise HTTPException(status_code=403, detail="Firm-scoped admins cannot create another firm.")
    firm = Firm(**request.model_dump())
    db.add(firm)
    db.commit()
    db.refresh(firm)
    return firm


@router.get("/firms", response_model=list[FirmRead])
def list_firms(
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Firm)
    if current_user.firm_id is not None:
        query = query.filter(Firm.firm_id == current_user.firm_id)
    return query.order_by(Firm.firm_id.asc()).offset(offset).limit(limit).all()


@router.get("/firms/{firm_id}", response_model=FirmRead)
def get_firm(
    firm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_firm_access(current_user, firm_id)
    return _get_firm_or_404(db, firm_id)


@router.patch("/firms/{firm_id}", response_model=FirmRead)
def update_firm(
    firm_id: int,
    request: FirmUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    _ensure_firm_access(current_user, firm_id)
    firm = _get_firm_or_404(db, firm_id)
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(firm, key, value)
    db.commit()
    db.refresh(firm)
    return firm


@router.delete("/firms/{firm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_firm(
    firm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    _ensure_firm_access(current_user, firm_id)
    firm = _get_firm_or_404(db, firm_id)
    db.delete(firm)
    db.commit()


# ---------------------------------------------------------------------------
# Matters
# ---------------------------------------------------------------------------

@router.post("/matters", response_model=MatterRead, status_code=status.HTTP_201_CREATED)
def create_matter(
    request: MatterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    _ensure_firm_access(current_user, request.firm_id)
    _get_firm_or_404(db, request.firm_id)
    matter = Matter(**request.model_dump())
    db.add(matter)
    db.commit()
    db.refresh(matter)
    return matter


@router.get("/matters", response_model=list[MatterRead])
def list_matters(
    firm_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.firm_id is not None:
        firm_id = current_user.firm_id
    query = db.query(Matter)
    if firm_id is not None:
        query = query.filter(Matter.firm_id == firm_id)
    return query.order_by(Matter.matter_id.asc()).offset(offset).limit(limit).all()


@router.get("/matters/{matter_id}", response_model=MatterRead)
def get_matter(
    matter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    matter = _get_matter_or_404(db, matter_id)
    _ensure_firm_access(current_user, matter.firm_id)
    return matter


@router.patch("/matters/{matter_id}", response_model=MatterRead)
def update_matter(
    matter_id: int,
    request: MatterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    matter = _get_matter_or_404(db, matter_id)
    _ensure_firm_access(current_user, matter.firm_id)
    data = request.model_dump(exclude_unset=True)
    if "firm_id" in data:
        _ensure_firm_access(current_user, data["firm_id"])
        _get_firm_or_404(db, data["firm_id"])
    for key, value in data.items():
        setattr(matter, key, value)
    db.commit()
    db.refresh(matter)
    return matter


@router.delete("/matters/{matter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_matter(
    matter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    matter = _get_matter_or_404(db, matter_id)
    _ensure_firm_access(current_user, matter.firm_id)
    db.delete(matter)
    db.commit()


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

@router.post("/budgets", response_model=BudgetRead, status_code=status.HTTP_201_CREATED)
def create_budget(
    request: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    matter = _get_matter_or_404(db, request.matter_id)
    _ensure_firm_access(current_user, matter.firm_id)
    if db.query(Budget).filter(Budget.matter_id == request.matter_id).first():
        raise HTTPException(status_code=400, detail="Matter already has a budget")
    budget = Budget(**request.model_dump())
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


@router.get("/budgets", response_model=list[BudgetRead])
def list_budgets(
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Budget).join(Budget.matter)
    if current_user.firm_id is not None:
        query = query.filter(Matter.firm_id == current_user.firm_id)
    return query.order_by(Budget.budget_id.asc()).offset(offset).limit(limit).all()


@router.get("/budgets/summary")
def list_budget_summaries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return canonical budget utilization for every accessible matter.

    Streamlit pages should use this endpoint instead of calculating
    utilization independently from raw ledger rows.
    """

    return get_all_budget_summaries(
        db=db,
        firm_id=current_user.firm_id,
    )


@router.get("/budgets/hierarchy")
def get_budget_hierarchy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Firm -> Matter -> Budget -> Invoice hierarchy for all budget UI."""
    return budget_hierarchy(db, firm_id=current_user.firm_id)


@router.get("/budgets/{budget_id}/summary")
def get_single_budget_summary(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the canonical utilization summary for one budget.
    """

    budget = db.get(Budget, budget_id)

    if budget is None:
        raise HTTPException(
            status_code=404,
            detail="Budget not found",
        )

    _ensure_firm_access(
        current_user,
        budget.matter.firm_id,
    )

    return get_budget_summary(
        db=db,
        matter_id=budget.matter_id,
    )


@router.get("/budgets/{budget_id}", response_model=BudgetRead)
def get_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    _ensure_firm_access(current_user, budget.matter.firm_id)
    return budget


@router.patch("/budgets/{budget_id}", response_model=BudgetRead)
def update_budget(
    budget_id: int,
    request: BudgetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    _ensure_firm_access(current_user, budget.matter.firm_id)
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(budget, key, value)
    db.commit()
    db.refresh(budget)
    return budget


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    _ensure_firm_access(current_user, budget.matter.firm_id)
    db.delete(budget)
    db.commit()


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@router.post("/invoices", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_invoice(
    request: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    matter = _get_matter_or_404(db, request.matter_id)
    _ensure_firm_access(current_user, request.firm_id)
    if matter.firm_id != request.firm_id:
        raise HTTPException(status_code=400, detail="Invoice firm_id does not match matter firm_id")
    invoice = Invoice(**request.model_dump())
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/invoices", response_model=list[InvoiceRead])
def list_invoices(
    matter_id: int | None = None,
    firm_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.firm_id is not None:
        firm_id = current_user.firm_id
    query = db.query(Invoice)
    if matter_id is not None:
        query = query.filter(Invoice.matter_id == matter_id)
    if firm_id is not None:
        query = query.filter(Invoice.firm_id == firm_id)
    return query.order_by(Invoice.invoice_id.desc()).offset(offset).limit(limit).all()


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = _get_invoice_or_404(db, invoice_id)
    _ensure_firm_access(current_user, invoice.firm_id)
    return invoice


@router.patch("/invoices/{invoice_id}", response_model=InvoiceRead)
def update_invoice(
    invoice_id: int,
    request: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    invoice = _get_invoice_or_404(db, invoice_id)
    _ensure_firm_access(current_user, invoice.firm_id)
    data = request.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(invoice, key, value)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.delete("/invoices/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    invoice = _get_invoice_or_404(db, invoice_id)
    _ensure_firm_access(current_user, invoice.firm_id)
    db.delete(invoice)
    db.commit()


# ---------------------------------------------------------------------------
# Line items
# ---------------------------------------------------------------------------

@router.post("/line-items", response_model=LineItemRead, status_code=status.HTTP_201_CREATED)
def create_line_item(
    request: LineItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    invoice = _get_invoice_or_404(db, request.invoice_id)
    _ensure_firm_access(current_user, invoice.firm_id)
    line_item = LineItem(**request.model_dump())
    db.add(line_item)
    db.commit()
    db.refresh(line_item)
    return line_item


@router.get("/line-items", response_model=list[LineItemRead])
def list_line_items(
    invoice_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(LineItem).join(LineItem.invoice)
    if current_user.firm_id is not None:
        query = query.filter(Invoice.firm_id == current_user.firm_id)
    if invoice_id is not None:
        query = query.filter(LineItem.invoice_id == invoice_id)
    return query.order_by(LineItem.line_item_id.asc()).offset(offset).limit(limit).all()


@router.get("/line-items/{line_item_id}", response_model=LineItemRead)
def get_line_item(
    line_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(LineItem, line_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Line item not found")
    _ensure_firm_access(current_user, item.invoice.firm_id)
    return item


@router.patch("/line-items/{line_item_id}", response_model=LineItemRead)
def update_line_item(
    line_item_id: int,
    request: LineItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    item = db.get(LineItem, line_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Line item not found")
    _ensure_firm_access(current_user, item.invoice.firm_id)
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/line-items/{line_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_line_item(
    line_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    item = db.get(LineItem, line_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Line item not found")
    _ensure_firm_access(current_user, item.invoice.firm_id)
    db.delete(item)
    db.commit()


# ---------------------------------------------------------------------------
# Budget ledger and alerts
# ---------------------------------------------------------------------------

@router.get("/budget-ledger", response_model=list[BudgetLedgerRead])
def list_budget_ledger(
    budget_id: int | None = None,
    invoice_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(BudgetLedger).join(BudgetLedger.budget).join(Budget.matter)
    if current_user.firm_id is not None:
        query = query.filter(Matter.firm_id == current_user.firm_id)
    if budget_id is not None:
        query = query.filter(BudgetLedger.budget_id == budget_id)
    if invoice_id is not None:
        query = query.filter(BudgetLedger.invoice_id == invoice_id)
    return query.order_by(BudgetLedger.ledger_id.desc()).offset(offset).limit(limit).all()


@router.post("/budget-ledger", response_model=BudgetLedgerRead, status_code=status.HTTP_201_CREATED)
def create_budget_ledger(
    request: BudgetLedgerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    budget = db.get(Budget, request.budget_id)
    invoice = db.get(Invoice, request.invoice_id)
    if budget is None or invoice is None:
        raise HTTPException(status_code=400, detail="budget_id and invoice_id must exist")
    _ensure_firm_access(current_user, budget.matter.firm_id)
    entry = BudgetLedger(**request.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _serialize_alert(db: Session, alert: Alert) -> dict:
    """Return an alert with current, user-facing business context.

    The Alert table intentionally stores only the alert/budget/invoice IDs.
    Frontend pages should not have to resolve database IDs themselves, so this
    serializer supplies firm, matter, invoice and current budget information.

    Utilization is calculated from the approved ledger.  If the alert is tied
    to a pending invoice, the invoice is also included in the projection so an
    over-budget/threshold alert shows the same projected utilization used by
    the budget-management service.
    """
    budget = db.get(Budget, alert.budget_id)
    matter = budget.matter if budget is not None else None
    firm = matter.firm if matter is not None else None
    invoice = db.get(Invoice, alert.invoice_id) if alert.invoice_id is not None else None

    allocated = float(budget.allocated_amt or 0) if budget else 0.0
    threshold = float(budget.threshold_pct or 0) if budget else None

    utilized = 0.0
    if budget is not None:
        utilized = float(
            db.query(func.coalesce(func.sum(BudgetLedger.amount), 0))
            .filter(
                BudgetLedger.budget_id == budget.budget_id,
                BudgetLedger.entry_type == "invoice_approved",
            )
            .scalar()
            or 0
        )

    invoice_is_pending = (
        invoice is not None
        and str(invoice.status).lower() == "pending_review"
    )

    projected_spend = utilized
    if invoice_is_pending:
        projected_spend += float(invoice.total_amount or 0)

    utilization_pct = (
        projected_spend / allocated * 100
        if allocated > 0
        else 0.0
    )
    remaining = allocated - projected_spend

    return {
        "alert_id": alert.alert_id,
        "budget_id": alert.budget_id,
        "invoice_id": alert.invoice_id,
        "type": alert.type,
        "alert_type": alert.type,
        "message": alert.message,
        "is_active": alert.is_active,
        "created_at": alert.created_at,
        "resolved_at": alert.resolved_at,
        "firm_id": firm.firm_id if firm else None,
        "firm_name": firm.name if firm else None,
        "firm_address": firm.address if firm else None,
        "matter_id": matter.matter_id if matter else None,
        "matter_no": matter.matter_no if matter else None,
        "matter_name": matter.name if matter else None,
        "invoice_no": invoice.invoice_no if invoice else None,
        "invoice_status": invoice.status if invoice else None,
        "invoice_amount": float(invoice.total_amount or 0) if invoice else None,
        "allocated": allocated,
        "utilized": utilized,
        "projected_spend": projected_spend,
        "remaining": remaining,
        "remaining_after_invoice": remaining,
        "utilization_pct": utilization_pct,
        "projected_utilization": utilization_pct,
        "threshold_pct": threshold,
    }


@router.get("/alerts")
def list_alerts(
    budget_id: int | None = None,
    active_only: bool = True,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return alerts enriched with current firm/matter/invoice context."""
    query = db.query(Alert).join(Alert.budget).join(Budget.matter)
    if current_user.firm_id is not None:
        query = query.filter(Matter.firm_id == current_user.firm_id)
    if budget_id is not None:
        query = query.filter(Alert.budget_id == budget_id)
    if active_only:
        query = query.filter(Alert.is_active.is_(True))

    alerts = (
        query.order_by(Alert.alert_id.desc())
        .offset(max(offset, 0))
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return [_serialize_alert(db, alert) for alert in alerts]


@router.post("/alerts", response_model=AlertRead, status_code=status.HTTP_201_CREATED)
def create_alert(
    request: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    budget = db.get(Budget, request.budget_id)
    if budget is None:
        raise HTTPException(status_code=400, detail="budget_id does not exist")
    _ensure_firm_access(current_user, budget.matter.firm_id)
    if request.invoice_id is not None:
        invoice = db.get(Invoice, request.invoice_id)
        if invoice is None:
            raise HTTPException(status_code=400, detail="invoice_id does not exist")
        if invoice.matter_id != budget.matter_id:
            raise HTTPException(
                status_code=422,
                detail="Alert invoice must belong to the budget's matter.",
            )

    alert = Alert(**request.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.patch("/alerts/{alert_id}/dismiss")
def dismiss_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    """Dismiss an alert without deleting its database history."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    budget = db.get(Budget, alert.budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget associated with this alert was not found")

    _ensure_firm_access(current_user, budget.matter.firm_id)

    if alert.is_active:
        alert.is_active = False
        alert.resolved_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(alert)

    return {
        "message": "Alert dismissed successfully.",
        "alert_id": alert.alert_id,
        "is_active": alert.is_active,
        "resolved_at": alert.resolved_at,
    }


# ---------------------------------------------------------------------------
# Automatic budget management hierarchy and adjustment history
# ---------------------------------------------------------------------------
@router.get("/budgets/{budget_id}/adjustments")
def list_budget_adjustments(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    matter = _get_matter_or_404(db, budget.matter_id)
    _ensure_firm_access(current_user, matter.firm_id)

    rows = (
        db.query(BudgetAdjustment)
        .filter(BudgetAdjustment.budget_id == budget_id)
        .order_by(BudgetAdjustment.adjustment_id.desc())
        .all()
    )
    result = []
    for row in rows:
        invoice = db.get(Invoice, row.invoice_id) if row.invoice_id is not None else None
        result.append({
            "adjustment_id": row.adjustment_id,
            "invoice_id": row.invoice_id,
            "invoice_no": invoice.invoice_no if invoice else None,
            "previous_amount": float(row.previous_amount),
            "adjustment_amount": float(row.adjustment_amount),
            "new_amount": float(row.new_amount),
            "adjustment_type": row.adjustment_type,
            "reason": row.reason,
            "confirmed": row.confirmed,
            "adjusted_by_user_id": row.adjusted_by_user_id,
            "created_at": row.created_at,
        })
    return result


@router.post("/budgets/{budget_id}/adjustments")
def create_budget_adjustment(
    budget_id: int,
    request: BudgetAdjustmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    matter = _get_matter_or_404(db, budget.matter_id)
    _ensure_firm_access(current_user, matter.firm_id)

    if request.invoice_id is not None:
        related = db.get(Invoice, request.invoice_id)
        if related is None or related.matter_id != budget.matter_id:
            raise HTTPException(
                status_code=422,
                detail="Related invoice must belong to this budget's matter.",
            )

    try:
        row = adjust_budget(
            db,
            budget=budget,
            amount=request.adjustment_amount,
            reason=request.reason,
            confirmed=request.confirmed,
            user=current_user,
            invoice_id=request.invoice_id,
        )
        reconciliation = reconcile_budget_after_adjustment(
            db,
            budget=budget,
            user=current_user,
        )
        db.commit()
        db.refresh(row)
        db.refresh(budget)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "adjustment_id": row.adjustment_id,
        "invoice_id": row.invoice_id,
        "previous_amount": float(row.previous_amount),
        "adjustment_amount": float(row.adjustment_amount),
        "new_amount": float(row.new_amount),
        "reason": row.reason,
        "confirmed": row.confirmed,
        "reconciliation": reconciliation,
        "message": (
            f"Budget {'increased' if row.adjustment_amount > 0 else 'decreased'} successfully. "
            f"{len(reconciliation['auto_approved'])} invoice(s) auto-approved after reconciliation; "
            f"{len(reconciliation['still_pending'])} still require review."
        ),
    }
