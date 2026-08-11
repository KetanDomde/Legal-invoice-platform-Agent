from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database.session import Base


class Matter(Base):
    __tablename__ = "matter"

    matter_id = Column(Integer, primary_key=True, autoincrement=True)
    firm_id = Column(Integer, ForeignKey("firm.firm_id"), nullable=False)
    name = Column(String, nullable=False)
    owner = Column(String, nullable=False)
    status = Column(String, nullable=False, default="open")

    firm = relationship("Firm", back_populates="matters")
    budget = relationship("Budget", back_populates="matter", uselist=False)
    invoices = relationship("Invoice", back_populates="matter")
