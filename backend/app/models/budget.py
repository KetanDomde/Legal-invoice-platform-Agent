from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.database.database import Base


class Budget(Base):
    __tablename__ = "budgets"

    budget_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    matter_id = Column(
        Integer,
        ForeignKey("matters.matter_id"),
        unique=True,
        nullable=False
    )

    allocated_amt = Column(
        Float,
        nullable=False
    )

    threshold_pct = Column(
        Float,
        default=80
    )

    # Relationships
    matter = relationship(
        "Matter",
        back_populates="budget"
    )