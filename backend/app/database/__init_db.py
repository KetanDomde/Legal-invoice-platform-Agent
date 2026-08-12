"""
Standalone script: creates all tables for models that are currently
implemented. Run with:  python -m app.database.__init_db

Matter is included as a TEMPORARY placeholder (owner: Rajat — see
app/models/matter.py docstring). Budget and Role aren't wired in yet, so
their tables won't be created until those land and get added below.
"""
from app.database.database import Base, engine

from app.models import (
    Firm,
    User,
    AuditLog,
    Invoice,
    LineItem,
    Matter,  # TEMPORARY placeholder — owner: Rajat, see app/models/matter.py docstring
)
# TODO(Rajat/Trinkesh): add Matter, Budget, Role back in here once built,
# and uncomment the matching lines in app/models/__init__.py.

Base.metadata.create_all(bind=engine)

print("Database tables created successfully.")