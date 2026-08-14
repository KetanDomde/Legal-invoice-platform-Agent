"""
Imports every model so it registers with Base.metadata before anything
calls create_all() — SQLAlchemy needs each model class actually imported
somewhere for its table to be known, even though nothing here directly
references the imported names.

FIXED during QA pass (14 Aug 2026): this used to import each model from
its own per-model shim file (app.models.user, app.models.invoice_item,
etc.), and one of those — app.models.invoice_item.LineItem — was
entirely commented out, so importing this module raised ImportError.
That broke every test in tests/test_api.py and tests/test_persistence.py
that depends on the _fresh_test_database fixture (see QA findings bug
#10). It also only listed 5 of the 9 real models (Budget, BudgetLedger,
and Alert were commented out as "pending" even though they've existed
and been in real use in app/models/entities.py since Day 4).

app/database/init_db.py — the actual production table-creation path —
already just imports app.models.entities directly and gets every model
in one shot. This module now does the same, instead of maintaining a
second, independently-drifting list of the same models.
"""
from app.database.database import Base
from app.models import entities  # noqa: F401 — registers every model with Base.metadata

# Kept for anything that still does `from app.database.base import User`
# etc. against this module specifically.
from app.models.entities import (  # noqa: F401
    Alert,
    AuditLog,
    Budget,
    BudgetLedger,
    Firm,
    Invoice,
    LineItem,
    Matter,
    User,
)