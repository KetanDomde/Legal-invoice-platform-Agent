from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import ADMIN, EDITOR, get_current_user, require_role
from app.database.database import get_db
from app.models import (
    Alert,
    Budget,
    BudgetAdjustment,
    BudgetLedger,
    Firm,
    Invoice,
    LineItem,
    Matter,
    User,
)
from app.schemas.billing import (
    AlertCreate,
    AlertRead,
    BudgetAdjustmentCreate,
    BudgetCreate,
    BudgetLedgerCreate,
    BudgetLedgerRead,
    BudgetRead,
    BudgetUpdate,
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
# from app.services.budget import (
#     get_all_budget_summaries,
#     get_budget_summary,
# )

from app.services.budget import (
    get_all_budget_summaries,
    get_budget_summary,
    get_invoice_budget_context as calculate_invoice_budget_context,
)
from app.services.budget_management import (
    adjust_budget,
    budget_hierarchy,
)

router = APIRouter(tags=["Billing"])


# ============================================================================
# Helper functions
# ============================================================================

def _ensure_firm_access(current_user: User, firm_id: int) -> None:
    """
    Ensure that a firm-scoped user cannot access another firm's data.

    A user without a firm_id is treated as a global/admin-level user.
    """
    if (
        current_user.firm_id is not None
        and current_user.firm_id != firm_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Permission denied",
        )


def _get_firm_or_404(db: Session, firm_id: int) -> Firm:
    """Return a firm or raise a 404 error."""
    firm = db.get(Firm, firm_id)

    if firm is None:
        raise HTTPException(
            status_code=404,
            detail="Firm not found",
        )

    return firm


def _get_matter_or_404(db: Session, matter_id: int) -> Matter:
    """Return a matter or raise a 404 error."""
    matter = db.get(Matter, matter_id)

    if matter is None:
        raise HTTPException(
            status_code=404,
            detail="Matter not found",
        )

    return matter


def _get_invoice_or_404(db: Session, invoice_id: int) -> Invoice:
    """Return an invoice or raise a 404 error."""
    invoice = db.get(Invoice, invoice_id)

    if invoice is None:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    return invoice


# ============================================================================
# Firms
# ============================================================================

@router.post(
    "/firms",
    response_model=FirmRead,
    status_code=status.HTTP_201_CREATED,
)
def create_firm(
    request: FirmCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    """Create a new firm."""

    if current_user.firm_id is not None:
        raise HTTPException(
            status_code=403,
            detail="Firm-scoped admins cannot create another firm.",
        )

    firm = Firm(**request.model_dump())

    db.add(firm)
    db.commit()
    db.refresh(firm)

    return firm


@router.get(
    "/firms",
    response_model=list[FirmRead],
)
def list_firms(
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List firms accessible to the current user."""

    query = db.query(Firm)

    if current_user.firm_id is not None:
        query = query.filter(
            Firm.firm_id == current_user.firm_id
        )

    return (
        query
        .order_by(Firm.firm_id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get(
    "/firms/{firm_id}",
    response_model=FirmRead,
)
def get_firm(
    firm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get one firm."""

    _ensure_firm_access(current_user, firm_id)

    return _get_firm_or_404(db, firm_id)


@router.patch(
    "/firms/{firm_id}",
    response_model=FirmRead,
)
def update_firm(
    firm_id: int,
    request: FirmUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    """Update a firm."""

    _ensure_firm_access(current_user, firm_id)

    firm = _get_firm_or_404(db, firm_id)

    for key, value in request.model_dump(
        exclude_unset=True
    ).items():
        setattr(firm, key, value)

    db.commit()
    db.refresh(firm)

    return firm


@router.delete(
    "/firms/{firm_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_firm(
    firm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    """Delete a firm."""

    _ensure_firm_access(current_user, firm_id)

    firm = _get_firm_or_404(db, firm_id)

    db.delete(firm)
    db.commit()


# ============================================================================
# Matters
# ============================================================================

@router.post(
    "/matters",
    response_model=MatterRead,
    status_code=status.HTTP_201_CREATED,
)
def create_matter(
    request: MatterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """Create a new matter."""

    _ensure_firm_access(
        current_user,
        request.firm_id,
    )

    _get_firm_or_404(
        db,
        request.firm_id,
    )

    matter = Matter(
        **request.model_dump()
    )

    db.add(matter)
    db.commit()
    db.refresh(matter)

    return matter


@router.get(
    "/matters",
    response_model=list[MatterRead],
)
def list_matters(
    firm_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List matters."""

    if current_user.firm_id is not None:
        firm_id = current_user.firm_id

    query = db.query(Matter)

    if firm_id is not None:
        query = query.filter(
            Matter.firm_id == firm_id
        )

    return (
        query
        .order_by(Matter.matter_id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get(
    "/matters/{matter_id}",
    response_model=MatterRead,
)
def get_matter(
    matter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get one matter."""

    matter = _get_matter_or_404(
        db,
        matter_id,
    )

    _ensure_firm_access(
        current_user,
        matter.firm_id,
    )

    return matter


@router.patch(
    "/matters/{matter_id}",
    response_model=MatterRead,
)
def update_matter(
    matter_id: int,
    request: MatterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """Update a matter."""

    matter = _get_matter_or_404(
        db,
        matter_id,
    )

    _ensure_firm_access(
        current_user,
        matter.firm_id,
    )

    data = request.model_dump(
        exclude_unset=True
    )

    if "firm_id" in data:
        _ensure_firm_access(
            current_user,
            data["firm_id"],
        )

        _get_firm_or_404(
            db,
            data["firm_id"],
        )

    for key, value in data.items():
        setattr(matter, key, value)

    db.commit()
    db.refresh(matter)

    return matter


@router.delete(
    "/matters/{matter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_matter(
    matter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    """Delete a matter."""

    matter = _get_matter_or_404(
        db,
        matter_id,
    )

    _ensure_firm_access(
        current_user,
        matter.firm_id,
    )

    db.delete(matter)
    db.commit()


# ============================================================================
# Budgets
# ============================================================================
#
# IMPORTANT ROUTING RULE:
#
# Static routes such as:
#     /budgets/hierarchy
#     /budgets/summary
#
# MUST be declared before:
#     /budgets/{budget_id}
#
# Otherwise FastAPI may interpret:
#     hierarchy
#
# as:
#     budget_id
#
# and fail because budget_id expects an integer.
# ============================================================================


@router.post(
    "/budgets",
    response_model=BudgetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_budget(
    request: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """Create a budget for a matter."""

    matter = _get_matter_or_404(
        db,
        request.matter_id,
    )

    _ensure_firm_access(
        current_user,
        matter.firm_id,
    )

    existing_budget = (
        db.query(Budget)
        .filter(
            Budget.matter_id == request.matter_id
        )
        .first()
    )

    if existing_budget:
        raise HTTPException(
            status_code=400,
            detail="Matter already has a budget",
        )

    budget = Budget(
        **request.model_dump()
    )

    db.add(budget)
    db.commit()
    db.refresh(budget)

    return budget


@router.get(
    "/budgets",
    response_model=list[BudgetRead],
)
def list_budgets(
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List budgets accessible to the current user."""

    query = (
        db.query(Budget)
        .join(Budget.matter)
    )

    if current_user.firm_id is not None:
        query = query.filter(
            Matter.firm_id == current_user.firm_id
        )

    return (
        query
        .order_by(Budget.budget_id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# ============================================================================
# STATIC BUDGET ROUTES
# These MUST come before /budgets/{budget_id}
# ============================================================================

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
    """
    Return the hierarchy used by the Budgets & Alerts page.

    Structure:
        Firm
          -> Matters
              -> Budget information
              -> Related invoices

    IMPORTANT:
    This static route is intentionally declared BEFORE
    /budgets/{budget_id}.

    Without this order, FastAPI may try to parse the word
    'hierarchy' as an integer budget_id.
    """

    return budget_hierarchy(
        db,
        firm_id=current_user.firm_id,
    )


# ============================================================================
# NESTED BUDGET ROUTES
# ============================================================================

@router.get("/budgets/{budget_id}/summary")
def get_single_budget_summary(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the canonical utilization summary for one budget.
    """

    budget = db.get(
        Budget,
        budget_id,
    )

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


@router.get("/budgets/{budget_id}/adjustments")
def list_budget_adjustments(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the complete adjustment history for a budget.

    This is used to show previous budget, adjustment amount,
    new budget, reason, confirmation, and related invoice.
    """

    budget = db.get(
        Budget,
        budget_id,
    )

    if budget is None:
        raise HTTPException(
            status_code=404,
            detail="Budget not found",
        )

    matter = _get_matter_or_404(
        db,
        budget.matter_id,
    )

    _ensure_firm_access(
        current_user,
        matter.firm_id,
    )

    rows = (
        db.query(BudgetAdjustment)
        .filter(
            BudgetAdjustment.budget_id == budget_id
        )
        .order_by(
            BudgetAdjustment.adjustment_id.desc()
        )
        .all()
    )

    return [
        {
            "adjustment_id": row.adjustment_id,
            "invoice_id": row.invoice_id,
            "previous_amount": float(
                row.previous_amount
            ),
            "adjustment_amount": float(
                row.adjustment_amount
            ),
            "new_amount": float(
                row.new_amount
            ),
            "adjustment_type": row.adjustment_type,
            "reason": row.reason,
            "confirmed": row.confirmed,
            "adjusted_by_user_id": (
                row.adjusted_by_user_id
            ),
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/budgets/{budget_id}/adjustments")
def create_budget_adjustment(
    budget_id: int,
    request: BudgetAdjustmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role([ADMIN])
    ),
):
    """
    Increase or decrease a budget.

    The budget management service handles:
    - Validation
    - Mandatory reason
    - Confirmation
    - Previous/new amount calculation
    - Adjustment history
    - Audit logging
    """

    budget = db.get(
        Budget,
        budget_id,
    )

    if budget is None:
        raise HTTPException(
            status_code=404,
            detail="Budget not found",
        )

    matter = _get_matter_or_404(
        db,
        budget.matter_id,
    )

    _ensure_firm_access(
        current_user,
        matter.firm_id,
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

        db.commit()
        db.refresh(row)

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )

    return {
        "adjustment_id": row.adjustment_id,
        "previous_amount": float(
            row.previous_amount
        ),
        "adjustment_amount": float(
            row.adjustment_amount
        ),
        "new_amount": float(
            row.new_amount
        ),
        "reason": row.reason,
        "confirmed": row.confirmed,
    }


# ============================================================================
# SIMPLE DYNAMIC BUDGET ROUTES
# Keep /budgets/{budget_id} AFTER static routes.
# ============================================================================

@router.get(
    "/budgets/{budget_id}",
    response_model=BudgetRead,
)
def get_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get one budget."""

    budget = db.get(
        Budget,
        budget_id,
    )

    if budget is None:
        raise HTTPException(
            status_code=404,
            detail="Budget not found",
        )

    _ensure_firm_access(
        current_user,
        budget.matter.firm_id,
    )

    return budget


@router.patch(
    "/budgets/{budget_id}",
    response_model=BudgetRead,
)
def update_budget(
    budget_id: int,
    request: BudgetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """Update an existing budget."""

    budget = db.get(
        Budget,
        budget_id,
    )

    if budget is None:
        raise HTTPException(
            status_code=404,
            detail="Budget not found",
        )

    _ensure_firm_access(
        current_user,
        budget.matter.firm_id,
    )

    for key, value in request.model_dump(
        exclude_unset=True
    ).items():
        setattr(budget, key, value)

    db.commit()
    db.refresh(budget)

    return budget


@router.delete(
    "/budgets/{budget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    """Delete a budget."""

    budget = db.get(
        Budget,
        budget_id,
    )

    if budget is None:
        raise HTTPException(
            status_code=404,
            detail="Budget not found",
        )

    _ensure_firm_access(
        current_user,
        budget.matter.firm_id,
    )

    db.delete(budget)
    db.commit()


# ============================================================================
# Invoices
# ============================================================================

@router.post(
    "/invoices",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_invoice(
    request: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """Create an invoice."""

    matter = _get_matter_or_404(
        db,
        request.matter_id,
    )

    _ensure_firm_access(
        current_user,
        request.firm_id,
    )

    if matter.firm_id != request.firm_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invoice firm_id does not match "
                "matter firm_id"
            ),
        )

    invoice = Invoice(
        **request.model_dump()
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return invoice


@router.get(
    "/invoices",
    response_model=list[InvoiceRead],
)
def list_invoices(
    matter_id: int | None = None,
    firm_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List invoices."""

    if current_user.firm_id is not None:
        firm_id = current_user.firm_id

    query = db.query(Invoice)

    if matter_id is not None:
        query = query.filter(
            Invoice.matter_id == matter_id
        )

    if firm_id is not None:
        query = query.filter(
            Invoice.firm_id == firm_id
        )

    return (
        query
        .order_by(Invoice.invoice_id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

# ---------------------------------------------------------------------------
# Invoice-level budget context
# ---------------------------------------------------------------------------

@router.get("/invoices/{invoice_id}/budget-context")
def get_invoice_budget_context(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return one complete budget view for a selected invoice.

    This endpoint is the single source of data for the Matter & Budget Context
    page.

    It separates three important concepts:

    1. Current actual budget position
       Calculated only from approved BudgetLedger entries.

    2. Projected impact of the selected invoice
       Shows what the budget would look like if this invoice is applied.
       If the invoice is already posted, it is not counted twice.

    3. Historical intake snapshot
       Preserves what the budget looked like when the invoice originally
       entered the system, even if the budget was adjusted later.
    """

    invoice = _get_invoice_or_404(
        db,
        invoice_id,
    )

    _ensure_firm_access(
        current_user,
        invoice.firm_id,
    )

    matter = _get_matter_or_404(
        db,
        invoice.matter_id,
    )

    firm = _get_firm_or_404(
        db,
        invoice.firm_id,
    )

    # ------------------------------------------------------------------------
    # Canonical current + projected budget calculation.
    #
    # The budget service handles the "already posted" check, so an approved
    # invoice is never added to the projection twice.
    # ------------------------------------------------------------------------

    budget_context = calculate_invoice_budget_context(
        db=db,
        invoice=invoice,
    )

    if not budget_context["has_budget"]:

        projected_status = "no_budget"

    elif budget_context["projected_over_budget"]:

        projected_status = "over_budget"

    elif (
        budget_context["projected_pct_used"]
        >= budget_context["threshold_pct"]
    ):

        projected_status = "threshold_reached"

    else:

        projected_status = "within_budget"

    budget_context[
        "projected_status"
    ] = projected_status

    # ------------------------------------------------------------------------
    # Related invoices.
    #
    # Same internal matter means the invoices belong to the same budget.
    # ------------------------------------------------------------------------

    related_invoice_rows = (
        db.query(Invoice)
        .filter(
            Invoice.matter_id
            == invoice.matter_id
        )
        .order_by(
            Invoice.invoice_id.desc()
        )
        .all()
    )

    related_invoices = []

    for related in related_invoice_rows:

        related_invoices.append(
            {
                "invoice_id": related.invoice_id,
                "invoice_no": related.invoice_no,
                "invoice_date": related.invoice_date,
                "total_amount": float(
                    related.total_amount
                    or 0
                ),
                "status": related.status,

                # These values preserve the result calculated when the
                # invoice entered the system.
                "budget_status_at_intake": getattr(
                    related,
                    "budget_status_at_intake",
                    None,
                ),
                "budget_attention_required": bool(
                    getattr(
                        related,
                        "budget_attention_required",
                        False,
                    )
                ),
                "budget_remaining_after_invoice": (
                    float(
                        related.budget_remaining_after_invoice
                    )
                    if getattr(
                        related,
                        "budget_remaining_after_invoice",
                        None,
                    )
                    is not None
                    else None
                ),

                # Lets the frontend highlight the selected invoice.
                "is_current": (
                    related.invoice_id
                    == invoice.invoice_id
                ),
            }
        )

    # ------------------------------------------------------------------------
    # Budget activity.
    #
    # Combine:
    #   - approved invoice postings from BudgetLedger
    #   - budget increases/decreases from BudgetAdjustment
    #
    # This is more business-friendly than exposing a raw ledger table only.
    # ------------------------------------------------------------------------

    budget_activity = []

    budget_id = budget_context.get(
        "budget_id"
    )

    if budget_id is not None:

        ledger_rows = (
            db.query(BudgetLedger)
            .filter(
                BudgetLedger.budget_id
                == budget_id
            )
            .order_by(
                BudgetLedger.created_at.desc()
            )
            .all()
        )

        for ledger_row in ledger_rows:

            ledger_invoice = db.get(
                Invoice,
                ledger_row.invoice_id,
            )

            budget_activity.append(
                {
                    "created_at": (
                        ledger_row.created_at
                    ),
                    "activity_type": (
                        "invoice_approved"
                    ),
                    "invoice_id": (
                        ledger_row.invoice_id
                    ),
                    "invoice_no": (
                        ledger_invoice.invoice_no
                        if ledger_invoice
                        else None
                    ),
                    "amount": float(
                        ledger_row.amount
                        or 0
                    ),

                    # A historical ledger row does not store a budget-after
                    # snapshot, so leave this empty rather than inventing one.
                    "budget_after": None,

                    "reason": None,
                    "confirmed": None,
                }
            )

        adjustment_rows = (
            db.query(BudgetAdjustment)
            .filter(
                BudgetAdjustment.budget_id
                == budget_id
            )
            .order_by(
                BudgetAdjustment.created_at.desc()
            )
            .all()
        )

        for adjustment in adjustment_rows:

            adjustment_invoice = (
                db.get(
                    Invoice,
                    adjustment.invoice_id,
                )
                if adjustment.invoice_id
                is not None
                else None
            )

            budget_activity.append(
                {
                    "created_at": (
                        adjustment.created_at
                    ),
                    "activity_type": (
                        f"budget_{adjustment.adjustment_type}"
                    ),
                    "invoice_id": (
                        adjustment.invoice_id
                    ),
                    "invoice_no": (
                        adjustment_invoice.invoice_no
                        if adjustment_invoice
                        else None
                    ),

                    # Positive for increase, negative for decrease.
                    "amount": float(
                        adjustment.adjustment_amount
                        or 0
                    ),

                    # BudgetAdjustment explicitly stores the new effective
                    # budget, so this value is historically accurate.
                    "budget_after": float(
                        adjustment.new_amount
                        or 0
                    ),

                    "reason": adjustment.reason,
                    "confirmed": adjustment.confirmed,
                }
            )

        # Show newest activity first.
        budget_activity.sort(
            key=lambda row: (
                row["created_at"]
                or ""
            ),
            reverse=True,
        )

    # ------------------------------------------------------------------------
    # Alerts for this budget.
    # ------------------------------------------------------------------------

    alerts = []

    if budget_id is not None:

        alert_rows = (
            db.query(Alert)
            .filter(
                Alert.budget_id
                == budget_id
            )
            .order_by(
                Alert.created_at.desc()
            )
            .all()
        )

        for alert in alert_rows:

            alerts.append(
                {
                    "alert_id": alert.alert_id,
                    "invoice_id": getattr(
                        alert,
                        "invoice_id",
                        None,
                    ),
                    "type": alert.type,
                    "message": alert.message,
                    "is_active": getattr(
                        alert,
                        "is_active",
                        True,
                    ),
                    "created_at": alert.created_at,
                }
            )

    # ------------------------------------------------------------------------
    # Historical intake snapshot.
    #
    # These values are intentionally preserved separately from the current
    # budget because an Admin may have increased/decreased the budget later.
    # ------------------------------------------------------------------------

    intake_snapshot = {
        "budget_id": getattr(
            invoice,
            "budget_id_at_intake",
            None,
        ),
        "budget_amount": (
            float(
                invoice.budget_amount_at_intake
            )
            if getattr(
                invoice,
                "budget_amount_at_intake",
                None,
            )
            is not None
            else None
        ),
        "used_before_invoice": (
            float(
                invoice.budget_used_before_invoice
            )
            if getattr(
                invoice,
                "budget_used_before_invoice",
                None,
            )
            is not None
            else None
        ),
        "projected_after_invoice": (
            float(
                invoice.budget_projected_after_invoice
            )
            if getattr(
                invoice,
                "budget_projected_after_invoice",
                None,
            )
            is not None
            else None
        ),
        "remaining_after_invoice": (
            float(
                invoice.budget_remaining_after_invoice
            )
            if getattr(
                invoice,
                "budget_remaining_after_invoice",
                None,
            )
            is not None
            else None
        ),
        "projected_pct": getattr(
            invoice,
            "budget_projected_pct",
            None,
        ),
        "status": getattr(
            invoice,
            "budget_status_at_intake",
            None,
        ),
        "attention_required": bool(
            getattr(
                invoice,
                "budget_attention_required",
                False,
            )
        ),
    }

    # ------------------------------------------------------------------------
    # Final response
    # ------------------------------------------------------------------------

    return {
        "invoice": {
            "invoice_id": invoice.invoice_id,
            "invoice_no": invoice.invoice_no,
            "invoice_date": invoice.invoice_date,
            "billing_period_start": getattr(
                invoice,
                "billing_period_start",
                None,
            ),
            "billing_period_end": getattr(
                invoice,
                "billing_period_end",
                None,
            ),
            "total_amount": float(
                invoice.total_amount
                or 0
            ),
            "status": invoice.status,
            "confidence_score": (
                invoice.confidence_score
            ),
        },

        "firm": {
            "firm_id": firm.firm_id,
            "name": firm.name,
            "address": getattr(
                firm,
                "address",
                None,
            ),
        },

        "matter": {
            "matter_id": matter.matter_id,
            "matter_no": getattr(
                matter,
                "matter_no",
                None,
            ),
            "name": matter.name,
            "owner": matter.owner,
            "status": matter.status,
        },

        "budget": budget_context,

        "intake_snapshot": intake_snapshot,

        "related_invoices": related_invoices,

        "budget_activity": budget_activity,

        "alerts": alerts,
    }

@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceRead,
)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get one invoice."""

    invoice = _get_invoice_or_404(
        db,
        invoice_id,
    )

    _ensure_firm_access(
        current_user,
        invoice.firm_id,
    )

    return invoice


@router.patch(
    "/invoices/{invoice_id}",
    response_model=InvoiceRead,
)
def update_invoice(
    invoice_id: int,
    request: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """Update an invoice."""

    invoice = _get_invoice_or_404(
        db,
        invoice_id,
    )

    _ensure_firm_access(
        current_user,
        invoice.firm_id,
    )

    data = request.model_dump(
        exclude_unset=True
    )

    for key, value in data.items():
        setattr(invoice, key, value)

    db.commit()
    db.refresh(invoice)

    return invoice


@router.delete(
    "/invoices/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    """Delete an invoice."""

    invoice = _get_invoice_or_404(
        db,
        invoice_id,
    )

    _ensure_firm_access(
        current_user,
        invoice.firm_id,
    )

    db.delete(invoice)
    db.commit()


# ============================================================================
# Line items
# ============================================================================

@router.post(
    "/line-items",
    response_model=LineItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_line_item(
    request: LineItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """Create a line item."""

    invoice = _get_invoice_or_404(
        db,
        request.invoice_id,
    )

    _ensure_firm_access(
        current_user,
        invoice.firm_id,
    )

    line_item = LineItem(
        **request.model_dump()
    )

    db.add(line_item)
    db.commit()
    db.refresh(line_item)

    return line_item


@router.get(
    "/line-items",
    response_model=list[LineItemRead],
)
def list_line_items(
    invoice_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List line items."""

    query = (
        db.query(LineItem)
        .join(LineItem.invoice)
    )

    if current_user.firm_id is not None:
        query = query.filter(
            Invoice.firm_id == current_user.firm_id
        )

    if invoice_id is not None:
        query = query.filter(
            LineItem.invoice_id == invoice_id
        )

    return (
        query
        .order_by(LineItem.line_item_id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get(
    "/line-items/{line_item_id}",
    response_model=LineItemRead,
)
def get_line_item(
    line_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get one line item."""

    item = db.get(
        LineItem,
        line_item_id,
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Line item not found",
        )

    _ensure_firm_access(
        current_user,
        item.invoice.firm_id,
    )

    return item


@router.patch(
    "/line-items/{line_item_id}",
    response_model=LineItemRead,
)
def update_line_item(
    line_item_id: int,
    request: LineItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """Update a line item."""

    item = db.get(
        LineItem,
        line_item_id,
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Line item not found",
        )

    _ensure_firm_access(
        current_user,
        item.invoice.firm_id,
    )

    for key, value in request.model_dump(
        exclude_unset=True
    ).items():
        setattr(item, key, value)

    db.commit()
    db.refresh(item)

    return item


@router.delete(
    "/line-items/{line_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_line_item(
    line_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    """Delete a line item."""

    item = db.get(
        LineItem,
        line_item_id,
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Line item not found",
        )

    _ensure_firm_access(
        current_user,
        item.invoice.firm_id,
    )

    db.delete(item)
    db.commit()


# ============================================================================
# Budget ledger
# ============================================================================

@router.get(
    "/budget-ledger",
    response_model=list[BudgetLedgerRead],
)
def list_budget_ledger(
    budget_id: int | None = None,
    invoice_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List budget ledger entries."""

    query = (
        db.query(BudgetLedger)
        .join(BudgetLedger.budget)
        .join(Budget.matter)
    )

    if current_user.firm_id is not None:
        query = query.filter(
            Matter.firm_id == current_user.firm_id
        )

    if budget_id is not None:
        query = query.filter(
            BudgetLedger.budget_id == budget_id
        )

    if invoice_id is not None:
        query = query.filter(
            BudgetLedger.invoice_id == invoice_id
        )

    return (
        query
        .order_by(BudgetLedger.ledger_id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post(
    "/budget-ledger",
    response_model=BudgetLedgerRead,
    status_code=status.HTTP_201_CREATED,
)
def create_budget_ledger(
    request: BudgetLedgerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    """Create a budget ledger entry."""

    budget = db.get(
        Budget,
        request.budget_id,
    )

    invoice = db.get(
        Invoice,
        request.invoice_id,
    )

    if budget is None or invoice is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "budget_id and invoice_id must exist"
            ),
        )

    _ensure_firm_access(
        current_user,
        budget.matter.firm_id,
    )

    entry = BudgetLedger(
        **request.model_dump()
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return entry


# ============================================================================
# Alerts
# ============================================================================

@router.get(
    "/alerts",
    response_model=list[AlertRead],
)
def list_alerts(
    budget_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List alerts."""

    query = (
        db.query(Alert)
        .join(Alert.budget)
        .join(Budget.matter)
    )

    if current_user.firm_id is not None:
        query = query.filter(
            Matter.firm_id == current_user.firm_id
        )

    if budget_id is not None:
        query = query.filter(
            Alert.budget_id == budget_id
        )

    return (
        query
        .order_by(Alert.alert_id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post(
    "/alerts",
    response_model=AlertRead,
    status_code=status.HTTP_201_CREATED,
)
def create_alert(
    request: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """Create an alert."""

    budget = db.get(
        Budget,
        request.budget_id,
    )

    if budget is None:
        raise HTTPException(
            status_code=400,
            detail="budget_id does not exist",
        )

    _ensure_firm_access(
        current_user,
        budget.matter.firm_id,
    )

    alert = Alert(
        **request.model_dump()
    )

    db.add(alert)
    db.commit()
    db.refresh(alert)

    return alert