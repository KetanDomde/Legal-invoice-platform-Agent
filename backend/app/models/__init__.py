"""Import every model module so Base.metadata sees all tables before create_all()."""
from app.models.user import User  # noqa: F401
from app.models.firm import Firm  # noqa: F401
from app.models.matter import Matter  # noqa: F401
from app.models.budget import Budget  # noqa: F401
from app.models.invoice import Invoice, LineItem  # noqa: F401
from app.models.ledger import BudgetLedger, Alert  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
