from sqlalchemy import Column, Integer, Float, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database.session import Base


class BudgetLedger(Base):
    __tablename__ = "budget_ledger"

    ledger_id = Column(Integer, primary_key=True, autoincrement=True)
    budget_id = Column(Integer, ForeignKey("budget.budget_id"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoice.invoice_id"), nullable=False)
    amount = Column(Float, nullable=False)
    entry_type = Column(String, nullable=False, default="invoice_approved")
    created_at = Column(String, nullable=False)

    budget = relationship("Budget", back_populates="ledger_entries")


class Alert(Base):
    __tablename__ = "alert"

    alert_id = Column(Integer, primary_key=True, autoincrement=True)
    budget_id = Column(Integer, ForeignKey("budget.budget_id"), nullable=False)
    type = Column(String, nullable=False)
    message = Column(String, nullable=False)
    created_at = Column(String, nullable=False)

    budget = relationship("Budget", back_populates="alerts")
