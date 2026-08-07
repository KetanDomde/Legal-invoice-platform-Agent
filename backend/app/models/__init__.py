"""
Import every model module here so that SQLModel/SQLAlchemy can resolve
all forward-referenced relationship strings ("Matter", "Invoice", ...)
before any table is used. Always import models from this package
(`from app.models import Firm, ...`), not from the individual files.
"""
from .firm import Firm, FirmCreate, FirmRead, FirmUpdate
from .matter import Matter, MatterCreate, MatterRead, MatterUpdate
from .budget import Budget, BudgetCreate, BudgetRead, BudgetUpdate
from .user import User, UserCreate, UserRead, UserUpdate
from .invoice import Invoice, InvoiceCreate, InvoiceRead, InvoiceUpdate
from .line_item import LineItem, LineItemCreate, LineItemRead, LineItemUpdate
from .budget_ledger import BudgetLedger, BudgetLedgerCreate, BudgetLedgerRead
from .alert import Alert, AlertCreate, AlertRead
from .audit_log import AuditLog, AuditLogCreate, AuditLogRead

__all__ = [
    "Firm", "FirmCreate", "FirmRead", "FirmUpdate",
    "Matter", "MatterCreate", "MatterRead", "MatterUpdate",
    "Budget", "BudgetCreate", "BudgetRead", "BudgetUpdate",
    "User", "UserCreate", "UserRead", "UserUpdate",
    "Invoice", "InvoiceCreate", "InvoiceRead", "InvoiceUpdate",
    "LineItem", "LineItemCreate", "LineItemRead", "LineItemUpdate",
    "BudgetLedger", "BudgetLedgerCreate", "BudgetLedgerRead",
    "Alert", "AlertCreate", "AlertRead",
    "AuditLog", "AuditLogCreate", "AuditLogRead",
]
