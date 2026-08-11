from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True,
    )

    invoice_id = Column(
        Integer,
        ForeignKey("invoices.invoice_id"),
        nullable=True,
    )

    action = Column(
        String(100),
        nullable=False,
    )

    notes = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # -------------------------
    # Relationships
    # -------------------------

    user = relationship(
        "User",
        back_populates="audit_logs",
    )

    invoice = relationship(
        "Invoice",
        back_populates="audit_logs",
    )