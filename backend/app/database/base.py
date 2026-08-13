"""
Imports every model so it registers with Base.metadata before anything
calls create_all() — SQLAlchemy needs each model class actually imported
somewhere for its table to be known, even though nothing here directly
references the imported names.

Only imports what's real today. Models that are still empty files or
don't exist yet are commented out with an owner + reason, so this module
is importable right now instead of crashing on someone else's unfinished
work. Uncomment each line as that model lands.
"""
from app.database.database import Base

from app.models.user import User
from app.models.firm import Firm
from app.models.audit_log import AuditLog
from app.models.invoice import Invoice
from app.models.invoice_item import LineItem
from app.models.matter import Matter  # TEMPORARY placeholder — owner: Rajat, see file docstring

# --- Pending — uncomment as each lands ---
# from app.models.role import Role          # owner: Trinkesh — file exists, currently empty (0 bytes)
# from app.models.budget import Budget      # owner: Rajat — file exists, currently empty (0 bytes)