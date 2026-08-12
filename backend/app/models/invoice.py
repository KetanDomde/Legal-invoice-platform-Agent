"""
Invoice model — owner: Bhushan (ERD: INVOICE entity).

This model uses a system-generated numeric `invoice_id` as the real
primary key, while preserving the user-visible invoice number as
`invoice_no` and requiring `matter_id` to be an alphanumeric string.
The combination of `invoice_no` + `matter_id` is unique, so the same
invoice cannot be stored twice for the same matter.

billing_period_start/end were requirements that were never actually
extracted or stored before this — added here alongside the extraction
prompt update in the workflow file.
"""
from sqlalchemy import Column, String, Integer, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database.database import Base


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("invoice_no", "matter_id", name="uix_invoice_no_matter"),
    )

    invoice_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    matter_id = Column(String, ForeignKey("matters.matter_id"), nullable=False)

    # No longer required at upload time (the new upload flow only asks
    # for invoice_id, matter_id, and the file) — nullable, best-effort
    # derived from the Matter row when one exists. See
    # routers/invoices.py's submit_invoice for exactly how.
    firm_id = Column(Integer, ForeignKey("firms.firm_id"), nullable=True)

    invoice_no = Column(String, nullable=True)          # AS PRINTED on the invoice (extracted) — informational now; invoice_id is the real identity, this is kept for display/audit
    invoice_date = Column(String, nullable=True)          # ISO date (YYYY-MM-DD), extracted from the PDF
    billing_period_start = Column(String, nullable=True)   # ISO date, extracted from the PDF
    billing_period_end = Column(String, nullable=True)     # ISO date, extracted from the PDF
    matter_name = Column(String, nullable=True)
    total_amount = Column(Float, nullable=True)

    # submitted / pending_review / approved / rejected / clarification_requested
    status = Column(String, nullable=False, default="submitted")

    confidence_score = Column(Float, nullable=True)     # 0-1, from extract_with_groq_call

    # --- Relationships to models that already exist ---
    firm = relationship("Firm", back_populates="invoices")
    matter = relationship("Matter", back_populates="invoices")
    audit_logs = relationship("AuditLog", back_populates="invoice")
    line_items = relationship("LineItem", back_populates="invoice", cascade="all, delete-orphan")