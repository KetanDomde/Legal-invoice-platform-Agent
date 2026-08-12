from datetime import date
from pydantic import BaseModel, Field


class ExtractedLineItem(BaseModel):
    timekeeper: str | None = None
    hours: float | None = Field(default=None, ge=0)
    rate: float | None = Field(default=None, ge=0)
    amount: float = Field(ge=0)


class ExtractedInvoice(BaseModel):
    invoice_no: str
    invoice_date: date | None = None
    total_amount: float = Field(ge=0)
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
