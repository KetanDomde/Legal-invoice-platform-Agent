from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database.session import Base


class User(Base):
    __tablename__ = "user"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin / editor / viewer — validated in app.auth
    firm_id = Column(Integer, ForeignKey("firm.firm_id"), nullable=True)

    firm = relationship("Firm", back_populates="users")
