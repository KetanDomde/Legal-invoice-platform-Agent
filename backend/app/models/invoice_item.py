"""
LineItem model — owner: Bhushan (ERD: LINE_ITEM entity).

The real, active LineItem model lives in app/models/entities.py (single
source of truth for every ORM model — see that file). This module used
to have its own LineItem class body entirely commented out, so
`from app.models.invoice_item import LineItem` raised ImportError —
which broke app/database/base.py and, through it, every test in
tests/test_api.py and tests/test_persistence.py (see QA findings bug
#10). Fixed by making this a thin re-export, matching the pattern
already used by app/models/matter.py, app/models/invoice.py, etc.,
instead of a second, divergent definition of the same table.
"""
from app.models.entities import LineItem

__all__ = ["LineItem"]

# --- Original commented-out class body, kept for reference only ---
# Fields match ERD.docx's LINE_ITEM table: line_item_id, invoice_id,
# timekeeper, hours, rate, amount — PLUS two extra columns (role,
# description) that are NOT in the ERD and are NOT on the real
# entities.LineItem model either (see QA findings bug #3 — persisting
# code never actually forwards these two fields today).
#
# class LineItem(Base):
#     __tablename__ = "line_items"

#     line_item_id = Column(Integer, primary_key=True, index=True)
#     invoice_id = Column(Integer, ForeignKey("invoices.invoice_id"), nullable=False)

#     # --- Extension beyond the ERD (part 2) — flag at next standup ---
#     # "fee" (a timekeeper billed hours at a rate) or "expense" (a flat
#     # cost like filing fees, courier — no timekeeper). Real legal e-billing
#     # (LEDES format) distinguishes these with different code series; this
#     # column is the lightweight equivalent so the frontend/dashboard can
#     # group/display them separately instead of expense lines silently
#     # looking like a timekeeper billed nothing. Added after a real bug was
#     # found: without an explicit type + a nullable timekeeper, the LLM was
#     # inventing a placeholder "UNKNOWN" timekeeper for expense lines.
#     line_type = Column(String, nullable=False, default="fee")

#     timekeeper = Column(String, nullable=True)   # name/role of the biller — legitimately NULL for expense lines
#     hours = Column(Float, nullable=True)
#     rate = Column(Float, nullable=True)
#     amount = Column(Float, nullable=False)        # hours x rate, or a flat expense amount

#     # --- Extension beyond the ERD — flag at next standup ---
#     # extract_with_groq_call() (workflows/legal_invoice_platform_agent.py)
#     # already returns `role` and `description` per line item (e.g. an
#     # expense line like "Filing Fee" has a description + amount but no
#     # timekeeper/hours/rate). The ERD's LINE_ITEM table doesn't define
#     # either column. Kept here so that real extracted data isn't silently
#     # dropped at persistence time — confirm with the team whether to keep
#     # both as real schema, or strip them in the repository layer to match
#     # the ERD exactly.
#     role = Column(String, nullable=True)
#     description = Column(String, nullable=True)

#     invoice = relationship("Invoice", back_populates="line_items")