from datetime import datetime
from pydantic import BaseModel
from datetime import date
from decimal import Decimal


class ReviewInvoiceResponse(BaseModel):

    invoice_id: int

    matter_id: int

    firm_id: int

    invoice_no: str | None = None

    invoice_date: date | None = None

    total_amount: Decimal | None = None

    status: str

    confidence_score: float | None = None

    budget_valid: bool | None = None

    duplicate_flag: bool = False

    validation_status: str | None = None

    validation_message: str | None = None

    review_reasons: list[str] = []
    
    
    class Config:
        from_attributes = True


class ApproveRequest(BaseModel):
    notes: str | None = None


class RejectRequest(BaseModel):
    reason: str


class ClarificationRequest(BaseModel):
    note: str