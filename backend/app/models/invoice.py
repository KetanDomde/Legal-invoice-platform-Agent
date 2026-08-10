from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Float,
    Boolean,
    Date,
    ForeignKey,
)


from sqlalchemy.orm import relationship

from app.database.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    invoice_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    matter_id = Column(
        Integer,
        ForeignKey("matters.matter_id"),
        nullable=False
    )

    firm_id = Column(
        Integer,
        ForeignKey("firms.firm_id"),
        nullable=False
    )

    invoice_no = Column(
        String,
        nullable=False
    )

    invoice_date = Column(
        String,
        nullable=False
    )

    total_amount = Column(
        Float,
        nullable=False
    )

    status = Column(
        String,
        default="submitted"
    )

    confidence_score = Column(
        Float,
        nullable=True
    )

    # Relationships
    matter = relationship(
        "Matter",
        back_populates="invoices"
    )

    firm = relationship(
        "Firm",
        back_populates="invoices"
    )

    audit_logs = relationship(
        "AuditLog",
        back_populates="invoice"
    )
    
    budget_valid = Column(
    Boolean,
    nullable=True,
    )

    duplicate_flag = Column(
    Boolean,
    nullable=False,
    default=False,
    )

    validation_status = Column(
    String,
    nullable=True,
    )

    validation_message = Column(
    String,
    nullable=True,
    )