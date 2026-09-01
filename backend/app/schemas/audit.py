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
    user_name: str | None = None

    # Business-friendly context. These are resolved by the audit API and are
    # intentionally separate from internal database IDs.
    invoice_no: str | None = None
    firm_name: str | None = None
    matter_no: str | None = None
    matter_name: str | None = None
    matter_label: str | None = None

    # Keep budget metadata available for budget-specific events.
    firm_id: int | None = None
    matter_id: int | None = None
    budget_id: int | None = None
    previous_value: str | None = None
    adjustment_amount: str | None = None
    new_value: str | None = None
    reason: str | None = None
    confirmed: bool | None = None

    model_config = {"from_attributes": True}

class AuditLogPage(BaseModel):
    items: list[AuditLogRead]
    total: int
    offset: int
    limit: int