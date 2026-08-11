from pydantic import BaseModel


class ValidationResponse(BaseModel):
    invoice_id: int
    decision: str
    reasons: list[str]
    status: str
    validation_passed: bool | None = None
    budget_ok: bool | None = None
    remaining_budget: float | None = None
    duplicate: bool | None = None
    duplicate_invoice_id: int | None = None
    confidence_score: float | None = None
    confidence_threshold: float | None = None
