from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database.database import Base

class LawFirm(Base):
    __tablename__ = "law_firms"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(255))
    invoices = relationship("Invoice", back_populates="law_firm")
    
    