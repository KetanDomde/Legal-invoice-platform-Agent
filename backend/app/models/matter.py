from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database.database import Base

class Matter(Base):
    __tablename__ = "matters"

    matter_id = Column(Integer, primary_key=True, index=True)

    firm_id = Column(
        Integer,
        ForeignKey("firms.firm_id"),
        nullable=False
    )

    name = Column(String, nullable=False)

    owner = Column(String, nullable=False)

    status = Column(String, default="open")

    # Relationships
    firm = relationship(
        "Firm",
        back_populates="matters"
    )

    budget = relationship(
        "Budget",
        back_populates="matter",
        uselist=False,
        cascade="all, delete"
    )

    invoices = relationship(
        "Invoice",
        back_populates="matter"
    )