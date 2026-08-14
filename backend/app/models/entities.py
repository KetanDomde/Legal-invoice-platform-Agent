from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text,UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Firm(Base):
    __tablename__ = "firms"

    firm_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    matters: Mapped[list["Matter"]] = relationship(back_populates="firm", cascade="all, delete-orphan")
    users: Mapped[list["User"]] = relationship(back_populates="firm")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="firm")


class Matter(Base):
    __tablename__ = "matters"

    matter_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)  # FIXED: str -> int
    matter_no: Mapped[Optional[str]] = mapped_column(String(50), index=True)   # ADD THIS LINE

    firm_id: Mapped[int] = mapped_column(ForeignKey("firms.firm_id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)

    firm: Mapped["Firm"] = relationship(back_populates="matters")
    budget: Mapped[Optional["Budget"]] = relationship(
        back_populates="matter",
        uselist=False,
        cascade="all, delete-orphan",
    )
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="matter")


class Budget(Base):
    __tablename__ = "budgets"

    budget_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    matter_id: Mapped[int] = mapped_column(
        ForeignKey("matters.matter_id"),
        unique=True,
        nullable=False,
        index=True,
    )
    allocated_amt: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_pct: Mapped[float] = mapped_column(Float, default=80, nullable=False)

    matter: Mapped["Matter"] = relationship(back_populates="budget")
    ledger_entries: Mapped[list["BudgetLedger"]] = relationship(
        back_populates="budget",
        cascade="all, delete-orphan",
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="budget",
        cascade="all, delete-orphan",
    )


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
    UniqueConstraint("invoice_no", "matter_id", name="uix_invoice_no_matter"),
)


    invoice_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True,autoincrement=True)
    matter_id: Mapped[int] = mapped_column(ForeignKey("matters.matter_id"), nullable=False, index=True)  # was int
    firm_id: Mapped[int] = mapped_column(ForeignKey("firms.firm_id"), nullable=False, index=True)
    invoice_no: Mapped[Optional[str]] = mapped_column(String(100), index=True)  # nullable now — extracted, not required
    invoice_date: Mapped[Optional[date]] = mapped_column(Date)
    billing_period_start: Mapped[Optional[date]] = mapped_column(Date)   # add — was missing
    billing_period_end: Mapped[Optional[date]] = mapped_column(Date)     # add — was missing
    matter_name: Mapped[Optional[str]] = mapped_column(String(255))  
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="submitted", nullable=False, index=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)

    budget_valid: Mapped[Optional[bool]] = mapped_column(Boolean)
    duplicate_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validation_status: Mapped[Optional[str]] = mapped_column(String(50))
    validation_message: Mapped[Optional[str]] = mapped_column(Text)

    matter: Mapped["Matter"] = relationship(back_populates="invoices")
    firm: Mapped["Firm"] = relationship(back_populates="invoices")
    line_items: Mapped[list["LineItem"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    
    ledger_entries: Mapped[list["BudgetLedger"]] = relationship(back_populates="invoice")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="invoice")


class LineItem(Base):
    __tablename__ = "line_items"

    line_item_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.invoice_id"), nullable=False, index=True)
    timekeeper: Mapped[Optional[str]] = mapped_column(String(255))
    hours: Mapped[Optional[float]] = mapped_column(Float)
    rate: Mapped[Optional[float]] = mapped_column(Float)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    invoice: Mapped["Invoice"] = relationship(back_populates="line_items")


class BudgetLedger(Base):
    __tablename__ = "budget_ledger"

    ledger_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.budget_id"), nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.invoice_id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(50), default="invoice_approved", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    budget: Mapped["Budget"] = relationship(back_populates="ledger_entries")
    invoice: Mapped["Invoice"] = relationship(back_populates="ledger_entries")


class Alert(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.budget_id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    budget: Mapped["Budget"] = relationship(back_populates="alerts")


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


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.user_id"), index=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.invoice_id"), index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")
    invoice: Mapped[Optional["Invoice"]] = relationship(back_populates="audit_logs")
