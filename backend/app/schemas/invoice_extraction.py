from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    # raise validation error when any of field value is UNKNOWN
    @model_validator(mode='after')
    def validate_no_unknown_values(self) -> 'ExtractedInvoice':
        # Check top-level string fields
        for field_name, value in self.model_dump(exclude={'line_items'}).items():
            if isinstance(value, str) and value.strip().upper() == "UNKNOWN":
                raise ValueError(f"Field '{field_name}' cannot be 'UNKNOWN'")
        return self


if __name__=="__main__":
    import json
    print(ExtractedInvoice.model_json_schema())