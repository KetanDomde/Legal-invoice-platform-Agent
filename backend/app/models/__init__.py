"""
Re-exports model classes so `from app.models import X` works — used by
__init_db.py and (later) by wherever else needs multiple models at once.

Only exports what's real today; see the commented block below for what's
still pending from other owners. Uncomment each line as that model lands
— also update __init_db.py's import list to match.
"""
from app.models.firm import Firm
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.invoice import Invoice
from app.models.invoice_item import LineItem
from app.models.matter import Matter  # TEMPORARY placeholder — owner: Rajat, see file docstring

# --- Pending — uncomment as each lands ---
# from app.models.role import Role          # owner: Trinkesh — file exists, currently empty (0 bytes)
# from app.models.budget import Budget      # owner: Rajat — file exists, currently empty (0 bytes)