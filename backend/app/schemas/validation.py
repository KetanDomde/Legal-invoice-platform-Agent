from pydantic import BaseModel, Field


class ValidationRequest(BaseModel):
    invoice_id: int
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)


class ValidationResponse(BaseModel):
    invoice_id: int
    validation_passed: bool
    budget_ok: bool
    remaining_budget: float
    duplicate: bool
    duplicate_invoice_id: int | None
    confidence_score: float | None
    confidence_threshold: float
    decision: str
    reasons: list[str]
