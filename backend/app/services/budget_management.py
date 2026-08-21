from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from app.models import Firm, Matter, Budget, BudgetLedger, BudgetAdjustment, Invoice, Alert, AuditLog, User
from app.models.entities import DEFAULT_BUDGET_AMOUNT, DEFAULT_THRESHOLD_PCT

def normalize(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().split())

def _audit(db: Session, action: str, *, user_id: int = -1, invoice_id=None, firm_id=None, matter_id=None, budget_id=None, notes=None, previous_value=None, adjustment_amount=None, new_value=None, reason=None, confirmed=None):
    db.add(AuditLog(user_id=user_id, invoice_id=invoice_id, action=action, notes=notes, firm_id=firm_id, matter_id=matter_id, budget_id=budget_id, previous_value=previous_value, adjustment_amount=adjustment_amount, new_value=new_value, reason=reason, confirmed=confirmed))

def resolve_or_create_from_invoice(db: Session, *, firm_name: str | None, firm_address: str | None, matter_no: str, matter_name: str | None, user_id: int = -1):
    matter_no = (matter_no or "").strip()
    if not matter_no:
        raise ValueError("A matter identifier is required to resolve the budget.")
    display_firm = (firm_name or "Unassigned Firm (Auto)").strip() or "Unassigned Firm (Auto)"
    display_address = (firm_address or "").strip() or None
    n_name, n_address = normalize(display_firm), normalize(display_address)
    firm = db.query(Firm).filter(Firm.normalized_name == n_name, Firm.normalized_address == n_address).first()
    if firm is None:
        firm = Firm(name=display_firm, address=display_address, normalized_name=n_name, normalized_address=n_address, status="active")
        db.add(firm); db.flush()
        _audit(db,"FIRM_AUTO_CREATED",user_id=user_id,firm_id=firm.firm_id,notes=f"Firm auto-created from invoice: {firm.name}")
    matter = db.query(Matter).filter(Matter.firm_id == firm.firm_id, Matter.matter_no == matter_no).first()
    created_matter = False
    if matter is None:
        matter = Matter(firm_id=firm.firm_id,matter_no=matter_no,name=(matter_name or f"Auto-created matter ({matter_no})").strip(),owner="Unassigned",status="open")
        db.add(matter); db.flush(); created_matter=True
        _audit(db,"MATTER_AUTO_CREATED",user_id=user_id,firm_id=firm.firm_id,matter_id=matter.matter_id,notes=f"Matter {matter_no} auto-created from invoice.")
    elif matter_name and normalize(matter.name) != normalize(matter_name):
        _audit(db,"MATTER_NAME_MISMATCH_DETECTED",user_id=user_id,firm_id=firm.firm_id,matter_id=matter.matter_id,notes=f"Existing name: {matter.name}; extracted name: {matter_name}. Matter ID remained authoritative.")
    budget = db.query(Budget).filter(Budget.matter_id == matter.matter_id).first()
    if budget is None:
        budget = Budget(matter_id=matter.matter_id,allocated_amt=DEFAULT_BUDGET_AMOUNT,threshold_pct=DEFAULT_THRESHOLD_PCT)
        db.add(budget); db.flush()
        _audit(db,"BUDGET_AUTO_CREATED",user_id=user_id,firm_id=firm.firm_id,matter_id=matter.matter_id,budget_id=budget.budget_id,notes=f"Default budget ${DEFAULT_BUDGET_AMOUNT:,.2f} created with {DEFAULT_THRESHOLD_PCT:.0f}% threshold.")
    return firm, matter, budget, created_matter

def budget_usage(db: Session, budget: Budget) -> float:
    return float(db.query(func.coalesce(func.sum(BudgetLedger.amount),0)).filter(BudgetLedger.budget_id==budget.budget_id,BudgetLedger.entry_type=="invoice_approved").scalar() or 0)

def apply_intake_snapshot(db: Session, invoice: Invoice, budget: Budget, user_id: int = -1):
    used = budget_usage(db,budget); allocated=float(budget.allocated_amt); amount=float(invoice.total_amount)
    projected=used+amount; remaining=allocated-projected; pct=(projected/allocated*100) if allocated else 0
    status = "within_budget" if pct < float(budget.threshold_pct) else ("threshold_reached" if pct <= 100 else "over_budget")
    invoice.budget_id_at_intake=budget.budget_id; invoice.budget_amount_at_intake=allocated; invoice.budget_used_before_invoice=used; invoice.budget_projected_after_invoice=projected; invoice.budget_remaining_after_invoice=remaining; invoice.budget_projected_pct=pct; invoice.budget_status_at_intake=status; invoice.budget_attention_required=status in ("threshold_reached","over_budget"); invoice.budget_valid=status != "over_budget"
    if status != "within_budget":
        typ="OVER_BUDGET_DETECTED" if status=="over_budget" else "BUDGET_THRESHOLD_REACHED"
        msg=(f"Invoice {invoice.invoice_no or invoice.invoice_id} would exceed budget by ${abs(remaining):,.2f}." if status=="over_budget" else f"Invoice {invoice.invoice_no or invoice.invoice_id} would take budget utilization to {pct:.1f}%.")
        db.add(Alert(budget_id=budget.budget_id,invoice_id=invoice.invoice_id,type=typ,message=msg,is_active=True))
        _audit(db,typ,user_id=user_id,invoice_id=invoice.invoice_id,firm_id=invoice.firm_id,matter_id=invoice.matter_id,budget_id=budget.budget_id,notes=msg)
    _audit(db,"INVOICE_ASSOCIATED_WITH_MATTER",user_id=user_id,invoice_id=invoice.invoice_id,firm_id=invoice.firm_id,matter_id=invoice.matter_id,budget_id=budget.budget_id,notes=f"Invoice associated with {invoice.matter.matter_no if invoice.matter else invoice.matter_id}.")
    return status

def adjust_budget(db: Session, *, budget: Budget, amount: float, reason: str, confirmed: bool, user: User, invoice_id: int | None = None):
    if not confirmed: raise ValueError("Budget adjustment must be explicitly confirmed.")
    if not reason or not reason.strip(): raise ValueError("A reason is required for every budget adjustment.")
    if amount == 0: raise ValueError("Adjustment amount cannot be zero.")
    previous=float(budget.allocated_amt); new=previous+float(amount)
    if new <= 0: raise ValueError("Budget cannot be zero or negative after adjustment.")
    adjustment=BudgetAdjustment(budget_id=budget.budget_id,invoice_id=invoice_id,adjusted_by_user_id=user.user_id,previous_amount=previous,adjustment_amount=amount,new_amount=new,adjustment_type="increase" if amount>0 else "decrease",reason=reason.strip(),confirmed=True)
    budget.allocated_amt=new; db.add(adjustment)
    matter=db.get(Matter,budget.matter_id)
    _audit(db,"BUDGET_INCREASED" if amount>0 else "BUDGET_DECREASED",user_id=user.user_id,invoice_id=invoice_id,firm_id=matter.firm_id if matter else None,matter_id=budget.matter_id,budget_id=budget.budget_id,previous_value=f"{previous:.2f}",adjustment_amount=f"{amount:+.2f}",new_value=f"{new:.2f}",reason=reason.strip(),confirmed=True,notes="Budget adjustment confirmed by admin.")
    return adjustment

def budget_hierarchy(db: Session, firm_id: int | None = None):
    q=db.query(Firm).options(joinedload(Firm.matters).joinedload(Matter.budget),joinedload(Firm.matters).joinedload(Matter.invoices)).order_by(Firm.name)
    if firm_id is not None: q=q.filter(Firm.firm_id==firm_id)
    result=[]
    for firm in q.all():
        matters=[]
        for matter in firm.matters:
            if not matter.budget: continue
            budget=matter.budget; used=budget_usage(db,budget); allocated=float(budget.allocated_amt); pct=(used/allocated*100) if allocated else 0
            invoices=[{"invoice_id":i.invoice_id,"invoice_no":i.invoice_no,"amount":float(i.total_amount),"status":i.status,"budget_status_at_intake":i.budget_status_at_intake,"remaining_after_invoice":float(i.budget_remaining_after_invoice) if i.budget_remaining_after_invoice is not None else None,"attention_required":i.budget_attention_required} for i in sorted(matter.invoices,key=lambda x:x.invoice_id,reverse=True)]
            matters.append({"matter_id":matter.matter_id,"matter_no":matter.matter_no,"matter_name":matter.name,"budget_id":budget.budget_id,"allocated":allocated,"utilized":used,"remaining":allocated-used,"pct_used":pct,"threshold_pct":float(budget.threshold_pct),"threshold_reached":pct>=float(budget.threshold_pct),"over_budget":pct>100,"invoices":invoices})
        if matters: result.append({"firm_id":firm.firm_id,"firm_name":firm.name,"firm_address":firm.address,"matters":matters})
    return result