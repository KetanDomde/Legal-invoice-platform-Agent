from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class BudgetBase(SQLModel):
    matter_id: int = Field(foreign_key="matter.matter_id", unique=True)
    allocated_amt: float
    threshold_pct: int = 80


class Budget(BudgetBase, table=True):
    __tablename__ = "budget"

    budget_id: Optional[int] = Field(default=None, primary_key=True)

    matter: Optional["Matter"] = Relationship(back_populates="budget")
    ledger_entries: List["BudgetLedger"] = Relationship(back_populates="budget")
    alerts: List["Alert"] = Relationship(back_populates="budget")


class BudgetCreate(BudgetBase):
    pass


class BudgetUpdate(SQLModel):
    allocated_amt: Optional[float] = None
    threshold_pct: Optional[int] = None


class BudgetRead(BudgetBase):
    budget_id: int
