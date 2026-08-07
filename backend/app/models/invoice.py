from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class InvoiceBase(SQLModel):
    matter_id: int = Field(foreign_key="matter.matter_id")
    invoice_no: str
    invoice_date: Optional[str] = None  # ISO date string
    total_amount: float
    status: str = "submitted"
    confidence_score: Optional[float] = None


class Invoice(InvoiceBase, table=True):
    __tablename__ = "invoice"

    invoice_id: Optional[int] = Field(default=None, primary_key=True)

    matter: Optional["Matter"] = Relationship(back_populates="invoices")
    line_items: List["LineItem"] = Relationship(back_populates="invoice")
    ledger_entries: List["BudgetLedger"] = Relationship(back_populates="invoice")
    audit_logs: List["AuditLog"] = Relationship(back_populates="invoice")


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(SQLModel):
    invoice_no: Optional[str] = None
    invoice_date: Optional[str] = None
    total_amount: Optional[float] = None
    status: Optional[str] = None
    confidence_score: Optional[float] = None


class InvoiceRead(InvoiceBase):
    invoice_id: int
