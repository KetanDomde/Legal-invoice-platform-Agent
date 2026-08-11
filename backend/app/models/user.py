from sqlalchemy import Column, Integer, String, ForeignKey,Boolean
from sqlalchemy.orm import relationship

from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    email = Column(String, unique=True, nullable=False, index=True)

    password_hash = Column(String, nullable=False)

    role = Column(String, nullable=False)

    firm_id = Column(Integer, ForeignKey("firms.firm_id"), nullable=True)

    # Relationships
    firm = relationship("Firm", back_populates="users")

    audit_logs = relationship(
        "AuditLog",
        back_populates="user"
    )
    
    is_active = Column(
    Boolean,
    nullable=False,
    default=True,
    )