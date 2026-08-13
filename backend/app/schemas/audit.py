from datetime import datetime
from pydantic import BaseModel


class AuditLogCreate(BaseModel):
    invoice_id: int | None = None
    user_id: int | None = None
    action: str
    notes: str | None = None


class AuditLogRead(AuditLogCreate):
    audit_id: int
    created_at: datetime
    model_config = {"from_attributes": True}
