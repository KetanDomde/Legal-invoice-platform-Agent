from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.database.database import Base


class Firm(Base):
    __tablename__ = "firms"

    firm_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contact_email = Column(String, nullable=True)
    status = Column(String, default="active")

    # Relationships
    matters = relationship("Matter", back_populates="firm")
    users = relationship("User", back_populates="firm")
    invoices = relationship("Invoice", back_populates="firm")