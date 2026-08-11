from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.database.session import Base


class Budget(Base):
    __tablename__ = "budget"

    budget_id = Column(Integer, primary_key=True, autoincrement=True)
    matter_id = Column(Integer, ForeignKey("matter.matter_id"), nullable=False, unique=True)
    allocated_amt = Column(Float, nullable=False)
    threshold_pct = Column(Float, nullable=False, default=80)

    matter = relationship("Matter", back_populates="budget")
    ledger_entries = relationship("BudgetLedger", back_populates="budget")
    alerts = relationship("Alert", back_populates="budget")
