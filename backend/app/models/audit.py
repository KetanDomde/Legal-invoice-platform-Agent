from sqlalchemy import Column, Integer, String, ForeignKey

from app.database.session import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoice.invoice_id"), nullable=True)
    user_id = Column(Integer, ForeignKey("user.user_id"), nullable=True)
    action = Column(String, nullable=False)
    notes = Column(String)
    timestamp = Column(String, nullable=False)
