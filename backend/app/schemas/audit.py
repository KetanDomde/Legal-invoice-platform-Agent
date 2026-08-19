from datetime import datetime
from pydantic import BaseModel


class AuditLogCreate(BaseModel):
    invoice_id: int | None = None
    user_id: int
    action: str
    notes: str | None = None
    request_id: str | None = None


class AuditLogRead(AuditLogCreate):
    audit_id: int
    created_at: datetime
    model_config = {"from_attributes": True}
    request_id: str | None = None
