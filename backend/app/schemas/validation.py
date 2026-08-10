from pydantic import BaseModel, Field

class ValidationRequest(BaseModel):
    
    matter_id: int
    firm_id: int
    invoice_no: str
    total_amount: float = Field(gt=0)
    confidence_score: float = Field(
        ge=0.0,
        le=1.0
    )
    invoice_id: int | None = None

class ValidationResponse(BaseModel):
    validation_passed: bool
    budget_ok: bool
    remaining_budget: float
    duplicate: bool
    duplicate_invoice_id: int | None
    confidence_score: float
    confidence_threshold: float
    decision: str
    reasons: list[str]
    

