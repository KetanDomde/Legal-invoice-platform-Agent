from datetime import date
from pydantic import BaseModel, Field


class ReviewInvoiceResponse(BaseModel):
    invoice_id: int
    matter_id: int
    firm_id: int
    invoice_no: str
    invoice_date: date | None
    total_amount: float
    status: str
    confidence_score: float | None
    budget_valid: bool | None
    duplicate_flag: bool
    validation_status: str | None
    validation_message: str | None
    review_reasons: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ApproveRequest(BaseModel):
    notes: str | None = None


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1)


class ClarificationRequest(BaseModel):
    reason: str = Field(min_length=1)
