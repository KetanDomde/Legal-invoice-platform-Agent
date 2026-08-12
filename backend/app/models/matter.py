"""
Matter model — owner: Rajat (ERD: MATTER entity).

*** TEMPORARY PLACEHOLDER — added by Bhushan, NOT Rajat's real build. ***

This file didn't exist at all, and its absence was a hard blocker for
EVERYONE, not just Invoice work: firm.py already declares
`matters = relationship("Matter", back_populates="firm")`, and
SQLAlchemy only resolves that name the first time ANY mapped class gets
instantiated (not at import time, not at create_all() time — confirmed
by testing). Until a `Matter` class existed somewhere, literally no ORM
insert/query worked for ANY model in the whole app.

Fields match ERD.docx's MATTER table exactly, so this is a faithful
shell — but it's scope-limited on purpose: no CRUD, no budget logic, no
validation, nothing beyond the bare columns + the one relationship
needed to unblock the mapper. Rajat should review and most likely
replace this file outright rather than build on top of it blindly.

DELETE THIS DOCSTRING NOTICE (or the whole placeholder) once real
ownership lands.
"""
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship

from app.database.database import Base


class Matter(Base):
    __tablename__ = "matters"

    matter_id = Column(String, primary_key=True, index=True)
    firm_id = Column(Integer, ForeignKey("firms.firm_id"), nullable=False)  # capstone scope: one primary firm per matter, per ERD note
    name = Column(String, nullable=False)
    owner = Column(String, nullable=False)   # internal matter owner (person), per ERD — NOT a FK to User in the ERD as written
    status = Column(String, nullable=False, default="open")  # open / closed

    firm = relationship("Firm", back_populates="matters")
    invoices = relationship("Invoice", back_populates="matter")