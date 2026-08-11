"""
Query helpers used by the API layer and the LangGraph agent. Rajat's
territory long-term (budget/ledger/reporting) with a couple of Trinkesh's
(audit log, duplicate check) — reference implementations so Day 4 is
testable now; swap individual functions for the real ones as they land,
same names/signatures.
"""
import datetime

from sqlalchemy.orm import Session

from app.models.budget import Budget
from app.models.ledger import BudgetLedger, Alert
from app.models.invoice import Invoice
from app.models.audit import AuditLog
from app.models.matter import Matter


def get_remaining_budget(db: Session, matter_id: int) -> dict:
    budget = db.query(Budget).filter(Budget.matter_id == matter_id).first()
    if not budget:
        return {"has_budget": False, "remaining": None, "allocated": None, "pct_used": None}
    spent = db.query(BudgetLedger).filter(BudgetLedger.budget_id == budget.budget_id).all()
    spent_amt = sum(e.amount for e in spent)
    remaining = budget.allocated_amt - spent_amt
    pct_used = (spent_amt / budget.allocated_amt * 100) if budget.allocated_amt else 0
    return {
        "has_budget": True,
        "budget_id": budget.budget_id,
        "allocated": budget.allocated_amt,
        "spent": spent_amt,
        "remaining": remaining,
        "pct_used": round(pct_used, 1),
        "threshold_pct": budget.threshold_pct,
    }


def check_duplicate_invoice(db: Session, invoice_no: str, firm_id: int) -> bool:
    return db.query(Invoice).filter(Invoice.invoice_no == invoice_no, Invoice.firm_id == firm_id).first() is not None


def insert_invoice(db: Session, matter_id: int, firm_id: int, invoice_no: str, invoice_date: str,
                    total_amount: float, confidence_score: float = None, status: str = "submitted") -> int:
    invoice = Invoice(
        matter_id=matter_id, firm_id=firm_id, invoice_no=invoice_no, invoice_date=invoice_date,
        total_amount=total_amount, confidence_score=confidence_score, status=status,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice.invoice_id


def get_invoice(db: Session, invoice_id: int):
    return db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()


def update_invoice_status(db: Session, invoice_id: int, new_status: str):
    db.query(Invoice).filter(Invoice.invoice_id == invoice_id).update({"status": new_status})
    db.commit()


def list_review_queue(db: Session, firm_id: int = None):
    q = db.query(Invoice).filter(Invoice.status == "pending_review")
    if firm_id is not None:
        q = q.filter(Invoice.firm_id == firm_id)
    return q.order_by(Invoice.invoice_id).all()


def write_audit_log(db: Session, action: str, invoice_id: int = None, user_id: int = None, notes: str = ""):
    log = AuditLog(
        invoice_id=invoice_id, user_id=user_id, action=action, notes=notes,
        timestamp=datetime.datetime.utcnow().isoformat(),
    )
    db.add(log)
    db.commit()


def record_ledger_entry(db: Session, budget_id: int, invoice_id: int, amount: float, entry_type: str = "invoice_approved"):
    entry = BudgetLedger(
        budget_id=budget_id, invoice_id=invoice_id, amount=amount, entry_type=entry_type,
        created_at=datetime.datetime.utcnow().isoformat(),
    )
    db.add(entry)
    db.commit()


def create_alert_if_threshold_crossed(db: Session, budget_id: int):
    budget = db.query(Budget).filter(Budget.budget_id == budget_id).first()
    if not budget:
        return None
    info = get_remaining_budget(db, budget.matter_id)
    pct_used = info["pct_used"] or 0
    if pct_used >= budget.threshold_pct:
        message = f"Budget {budget_id} at {pct_used:.1f}% of allocated ${budget.allocated_amt:.2f} (threshold {budget.threshold_pct}%)."
        alert = Alert(budget_id=budget_id, type="threshold_warning", message=message,
                       created_at=datetime.datetime.utcnow().isoformat())
        db.add(alert)
        db.commit()
        return message
    return None


def get_reports_summary(db: Session, matter_id: int = None, firm_id: int = None) -> dict:
    q = db.query(Invoice)
    if matter_id is not None:
        q = q.filter(Invoice.matter_id == matter_id)
    if firm_id is not None:
        q = q.filter(Invoice.firm_id == firm_id)
    invoices = q.all()

    status_breakdown = {}
    for inv in invoices:
        row = status_breakdown.setdefault(inv.status, {"status": inv.status, "count": 0, "total": 0.0})
        row["count"] += 1
        row["total"] += inv.total_amount

    spend_by_matter = {}
    for inv in invoices:
        if inv.status != "approved":
            continue
        matter = db.query(Matter).filter(Matter.matter_id == inv.matter_id).first()
        row = spend_by_matter.setdefault(inv.matter_id, {
            "matter_id": inv.matter_id, "matter_name": matter.name if matter else None, "spend": 0.0,
        })
        row["spend"] += inv.total_amount

    budgets = db.query(Budget).all()
    utilization = []
    for b in budgets:
        info = get_remaining_budget(db, b.matter_id)
        utilization.append({
            "budget_id": b.budget_id, "matter_id": b.matter_id,
            "allocated": b.allocated_amt, "spent": info["spent"], "pct_used": info["pct_used"],
        })

    return {
        "invoice_status_breakdown": list(status_breakdown.values()),
        "spend_by_matter": list(spend_by_matter.values()),
        "budget_utilization": utilization,
    }


def create_matter(db: Session, firm_id: int, name: str, owner: str) -> int:
    matter = Matter(firm_id=firm_id, name=name, owner=owner)
    db.add(matter)
    db.commit()
    db.refresh(matter)
    return matter.matter_id


def create_budget(db: Session, matter_id: int, allocated_amt: float, threshold_pct: float = 80) -> int:
    budget = Budget(matter_id=matter_id, allocated_amt=allocated_amt, threshold_pct=threshold_pct)
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget.budget_id
