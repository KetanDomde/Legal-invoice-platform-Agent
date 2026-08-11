from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import ADMIN, EDITOR, get_current_user, require_role
from app.database.database import get_db
from app.models import Alert, Budget, BudgetLedger, Firm, Invoice, LineItem, Matter, User
from app.schemas.billing import (
    AlertCreate,
    AlertRead,
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


@router.get("/alerts", response_model=list[AlertRead])
def list_alerts(
    budget_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Alert).join(Alert.budget).join(Budget.matter)
    if current_user.firm_id is not None:
        query = query.filter(Matter.firm_id == current_user.firm_id)
    if budget_id is not None:
        query = query.filter(Alert.budget_id == budget_id)
    return query.order_by(Alert.alert_id.desc()).offset(offset).limit(limit).all()


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
    alert = Alert(**request.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
