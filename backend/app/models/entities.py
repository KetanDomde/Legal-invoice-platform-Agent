from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.database import Base

DEFAULT_BUDGET_AMOUNT = 100000.0
DEFAULT_THRESHOLD_PCT = 80.0

class Firm(Base):
    __tablename__ = "firms"
    __table_args__ = (UniqueConstraint("normalized_name", "normalized_address", name="uix_firm_normalized_name_address"),)
    firm_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)
    # Used only for matching so ABC/abc and spacing variations do not duplicate firms.
    normalized_name: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    normalized_address: Mapped[Optional[str]] = mapped_column(Text)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    matters: Mapped[list["Matter"]] = relationship(back_populates="firm", cascade="all, delete-orphan")
    users: Mapped[list["User"]] = relationship(back_populates="firm")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="firm")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="firm")

class Matter(Base):
    __tablename__ = "matters"
    __table_args__ = (UniqueConstraint("firm_id", "matter_no", name="uix_matter_firm_matter_no"),)
    matter_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    # Business identifier from invoice. Same firm + same matter_no = same matter.
    matter_no: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    firm_id: Mapped[int] = mapped_column(ForeignKey("firms.firm_id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, default="Unassigned")
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    firm: Mapped["Firm"] = relationship(back_populates="matters")
    budget: Mapped[Optional["Budget"]] = relationship(back_populates="matter", uselist=False, cascade="all, delete-orphan")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="matter")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="matter")

class Budget(Base):
    __tablename__ = "budgets"
    budget_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    matter_id: Mapped[int] = mapped_column(ForeignKey("matters.matter_id"), unique=True, nullable=False, index=True)
    allocated_amt: Mapped[float] = mapped_column(Numeric(14,2), default=DEFAULT_BUDGET_AMOUNT, nullable=False)
    threshold_pct: Mapped[float] = mapped_column(Float, default=DEFAULT_THRESHOLD_PCT, nullable=False)
    matter: Mapped["Matter"] = relationship(back_populates="budget")
    ledger_entries: Mapped[list["BudgetLedger"]] = relationship(back_populates="budget", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="budget", cascade="all, delete-orphan")
    adjustments: Mapped[list["BudgetAdjustment"]] = relationship(back_populates="budget", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="budget")

class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("invoice_no", "matter_id", name="uix_invoice_no_matter"),)
    invoice_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    matter_id: Mapped[int] = mapped_column(ForeignKey("matters.matter_id"), nullable=False, index=True)
    firm_id: Mapped[int] = mapped_column(ForeignKey("firms.firm_id"), nullable=False, index=True)
    invoice_no: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    invoice_date: Mapped[Optional[date]] = mapped_column(Date)
    billing_period_start: Mapped[Optional[date]] = mapped_column(Date)
    billing_period_end: Mapped[Optional[date]] = mapped_column(Date)
    matter_name: Mapped[Optional[str]] = mapped_column(String(255))
    total_amount: Mapped[float] = mapped_column(Numeric(14,2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="submitted", nullable=False, index=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    budget_valid: Mapped[Optional[bool]] = mapped_column(Boolean)
    duplicate_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validation_status: Mapped[Optional[str]] = mapped_column(String(50))
    validation_message: Mapped[Optional[str]] = mapped_column(Text)
    # Snapshot preserves what budget looked like at intake even after later adjustments.
    budget_id_at_intake: Mapped[Optional[int]] = mapped_column(ForeignKey("budgets.budget_id"), index=True)
    budget_amount_at_intake: Mapped[Optional[float]] = mapped_column(Numeric(14,2))
    budget_used_before_invoice: Mapped[Optional[float]] = mapped_column(Numeric(14,2))
    budget_projected_after_invoice: Mapped[Optional[float]] = mapped_column(Numeric(14,2))
    budget_remaining_after_invoice: Mapped[Optional[float]] = mapped_column(Numeric(14,2))
    budget_projected_pct: Mapped[Optional[float]] = mapped_column(Float)
    budget_status_at_intake: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    budget_attention_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    matter: Mapped["Matter"] = relationship(back_populates="invoices")
    firm: Mapped["Firm"] = relationship(back_populates="invoices")
    line_items: Mapped[list["LineItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    ledger_entries: Mapped[list["BudgetLedger"]] = relationship(back_populates="invoice")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="invoice")
    budget_adjustments: Mapped[list["BudgetAdjustment"]] = relationship(back_populates="related_invoice")

class LineItem(Base):
    __tablename__ = "line_items"
    line_item_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.invoice_id"), nullable=False, index=True)
    # fee = timekeeper professional charge; expense = flat reimbursable cost.
    line_type: Mapped[str] = mapped_column(String(20), nullable=False, default="fee", index=True)
    timekeeper: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    hours: Mapped[Optional[float]] = mapped_column(Float)
    rate: Mapped[Optional[float]] = mapped_column(Float)
    amount: Mapped[float] = mapped_column(Numeric(14,2), nullable=False)
    invoice: Mapped["Invoice"] = relationship(back_populates="line_items")

class BudgetLedger(Base):
    __tablename__ = "budget_ledger"
    __table_args__ = (UniqueConstraint("budget_id", "invoice_id", "entry_type", name="uix_budget_ledger_budget_invoice_type"),)
    ledger_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.budget_id"), nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.invoice_id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(14,2), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(50), default="invoice_approved", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    budget: Mapped["Budget"] = relationship(back_populates="ledger_entries")
    invoice: Mapped["Invoice"] = relationship(back_populates="ledger_entries")

class BudgetAdjustment(Base):
    __tablename__ = "budget_adjustments"
    adjustment_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.budget_id"), nullable=False, index=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.invoice_id"), index=True)
    adjusted_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.user_id"), index=True)
    previous_amount: Mapped[float] = mapped_column(Numeric(14,2), nullable=False)
    adjustment_amount: Mapped[float] = mapped_column(Numeric(14,2), nullable=False)
    new_amount: Mapped[float] = mapped_column(Numeric(14,2), nullable=False)
    adjustment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    budget: Mapped["Budget"] = relationship(back_populates="adjustments")
    related_invoice: Mapped[Optional["Invoice"]] = relationship(back_populates="budget_adjustments")
    adjusted_by: Mapped[Optional["User"]] = relationship(back_populates="budget_adjustments")

class Alert(Base):
    __tablename__ = "alerts"
    alert_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.budget_id"), nullable=False, index=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.invoice_id"), index=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    budget: Mapped["Budget"] = relationship(back_populates="alerts")
    invoice: Mapped[Optional["Invoice"]] = relationship()

class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="viewer", nullable=False)
    firm_id: Mapped[Optional[int]] = mapped_column(ForeignKey("firms.firm_id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    firm: Mapped[Optional["Firm"]] = relationship(back_populates="users")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")
    budget_adjustments: Mapped[list["BudgetAdjustment"]] = relationship(back_populates="adjusted_by")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    audit_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.invoice_id"), index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    # Nullable so existing generic audit rows remain compatible.
    firm_id: Mapped[Optional[int]] = mapped_column(ForeignKey("firms.firm_id"), index=True)
    matter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("matters.matter_id"), index=True)
    budget_id: Mapped[Optional[int]] = mapped_column(ForeignKey("budgets.budget_id"), index=True)
    previous_value: Mapped[Optional[str]] = mapped_column(String(255))
    adjustment_amount: Mapped[Optional[str]] = mapped_column(String(255))
    new_value: Mapped[Optional[str]] = mapped_column(String(255))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    confirmed: Mapped[Optional[bool]] = mapped_column(Boolean)
    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")
    invoice: Mapped[Optional["Invoice"]] = relationship(back_populates="audit_logs")
    firm: Mapped[Optional["Firm"]] = relationship(back_populates="audit_logs")
    matter: Mapped[Optional["Matter"]] = relationship(back_populates="audit_logs")
    budget: Mapped[Optional["Budget"]] = relationship(back_populates="audit_logs")
    @property
    def user_name(self) -> Optional[str]:
        return self.user.name if self.user is not None else None