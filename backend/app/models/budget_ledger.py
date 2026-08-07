from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BudgetLedgerBase(SQLModel):
    budget_id: int = Field(foreign_key="budget.budget_id")
    invoice_id: int = Field(foreign_key="invoice.invoice_id")
    amount: float
    entry_type: str = "invoice_approved"
    created_at: str = Field(default_factory=_now_iso)


class BudgetLedger(BudgetLedgerBase, table=True):
    __tablename__ = "budget_ledger"

    ledger_id: Optional[int] = Field(default=None, primary_key=True)

    budget: Optional["Budget"] = Relationship(back_populates="ledger_entries")
    invoice: Optional["Invoice"] = Relationship(back_populates="ledger_entries")


class BudgetLedgerCreate(SQLModel):
    budget_id: int
    invoice_id: int
    amount: float
    entry_type: str = "invoice_approved"
    created_at: Optional[str] = None  # server fills in if omitted


class BudgetLedgerRead(BudgetLedgerBase):
    ledger_id: int
