from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.database.session import Base


class Firm(Base):
    __tablename__ = "firm"

    firm_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    contact_email = Column(String)
    status = Column(String, nullable=False, default="active")

    users = relationship("User", back_populates="firm")
    matters = relationship("Matter", back_populates="firm")
