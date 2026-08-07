from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLogBase(SQLModel):
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.invoice_id")
    user_id: Optional[int] = Field(default=None, foreign_key="user.user_id")
    action: str
    notes: Optional[str] = None
    timestamp: str = Field(default_factory=_now_iso)


class AuditLog(AuditLogBase, table=True):
    __tablename__ = "audit_log"

    log_id: Optional[int] = Field(default=None, primary_key=True)

    invoice: Optional["Invoice"] = Relationship(back_populates="audit_logs")
    user: Optional["User"] = Relationship(back_populates="audit_logs")


class AuditLogCreate(SQLModel):
    invoice_id: Optional[int] = None
    user_id: Optional[int] = None
    action: str
    notes: Optional[str] = None
    timestamp: Optional[str] = None


class AuditLogRead(AuditLogBase):
    log_id: int
