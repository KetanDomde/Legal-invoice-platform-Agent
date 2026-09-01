from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExtractedLineItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_type: Literal["fee", "expense"] | None = None
    timekeeper: str | None = None
    role: str | None = None
    description: str | None = None
    hours: float | None = Field(default=None, ge=0)
    rate: float | None = Field(default=None, ge=0)
    amount: float = Field(ge=0)


class ExtractedInvoice(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_no: str
    invoice_date: date
    total_amount: float = Field(ge=0)
    line_items: list[ExtractedLineItem] = Field(default_factory=list)

if __name__=="__main__":
    import json
    print(ExtractedInvoice.model_json_schema())