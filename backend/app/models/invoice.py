from sqlalchemy import Column, Integer, Float, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database.session import Base


class Invoice(Base):
    __tablename__ = "invoice"

    invoice_id = Column(Integer, primary_key=True, autoincrement=True)
    matter_id = Column(Integer, ForeignKey("matter.matter_id"), nullable=False)
    firm_id = Column(Integer, ForeignKey("firm.firm_id"), nullable=False)
    invoice_no = Column(String, nullable=False)
    invoice_date = Column(String, nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="submitted")
    confidence_score = Column(Float)

    matter = relationship("Matter", back_populates="invoices")
    line_items = relationship("LineItem", back_populates="invoice")


class LineItem(Base):
    __tablename__ = "line_item"

    line_item_id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoice.invoice_id"), nullable=False)
    timekeeper = Column(String)
    hours = Column(Float)
    rate = Column(Float)
    amount = Column(Float, nullable=False)

    invoice = relationship("Invoice", back_populates="line_items")
