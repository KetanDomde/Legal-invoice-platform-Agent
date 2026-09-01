from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field

class FirmCreate(BaseModel):
    name:str; address:str|None=None; contact_email:EmailStr|None=None; status:str="active"
class FirmUpdate(BaseModel):
    name:str|None=None; address:str|None=None; contact_email:EmailStr|None=None; status:str|None=None
class FirmRead(FirmCreate):
    firm_id:int; model_config={"from_attributes":True}
class MatterCreate(BaseModel):
    firm_id:int; matter_no:str|None=None; name:str; owner:str="Unassigned"; status:str="open"
class MatterUpdate(BaseModel):
    firm_id:int|None=None; matter_no:str|None=None; name:str|None=None; owner:str|None=None; status:str|None=None
class MatterRead(MatterCreate):
    matter_id:int; model_config={"from_attributes":True}
class BudgetCreate(BaseModel):
    matter_id:int; allocated_amt:float=Field(default=100000.0,gt=0); threshold_pct:float=Field(default=80,ge=0,le=100)
class BudgetUpdate(BaseModel):
    allocated_amt:float|None=Field(default=None,gt=0); threshold_pct:float|None=Field(default=None,ge=0,le=100)
class BudgetRead(BudgetCreate):
    budget_id:int; model_config={"from_attributes":True}
class BudgetAdjustmentCreate(BaseModel):
    adjustment_amount:float
    reason:str=Field(min_length=1)
    confirmed:bool
    invoice_id:int|None=None
class InvoiceCreate(BaseModel):
    matter_id:int; firm_id:int; invoice_no:str; invoice_date:date|None=None; total_amount:float=Field(gt=0); status:str="submitted"; confidence_score:float|None=Field(default=None,ge=0,le=1)
class InvoiceUpdate(BaseModel):
    invoice_no:str|None=None; invoice_date:date|None=None; total_amount:float|None=Field(default=None,gt=0); status:str|None=None; confidence_score:float|None=Field(default=None,ge=0,le=1)
class InvoiceRead(InvoiceCreate):
    invoice_id:int; budget_valid:bool|None=None; duplicate_flag:bool=False; validation_status:str|None=None; validation_message:str|None=None; budget_status_at_intake:str|None=None; budget_attention_required:bool=False; model_config={"from_attributes":True}
class LineItemCreate(BaseModel):
    invoice_id: int
    line_type: str = "fee"
    timekeeper: str | None = None
    role: str | None = None
    description: str | None = None
    hours: float | None = Field(default=None, ge=0)
    rate: float | None = Field(default=None, ge=0)
    amount: float = Field(gt=0)
class LineItemUpdate(BaseModel):
    line_type: str | None = None
    timekeeper: str | None = None
    role: str | None = None
    description: str | None = None
    hours: float | None = Field(default=None, ge=0)
    rate: float | None = Field(default=None, ge=0)
    amount: float | None = Field(default=None, gt=0)
class LineItemRead(LineItemCreate):
    line_item_id:int; model_config={"from_attributes":True}
class BudgetLedgerCreate(BaseModel):
    budget_id:int; invoice_id:int; amount:float=Field(gt=0); entry_type:str="invoice_approved"
class BudgetLedgerRead(BudgetLedgerCreate):
    ledger_id:int; created_at:datetime; model_config={"from_attributes":True}
class AlertCreate(BaseModel):
    budget_id:int; type:str; message:str; invoice_id:int|None=None
class AlertRead(AlertCreate):
    alert_id:int; created_at:datetime; is_active:bool=True; model_config={"from_attributes":True}
class UserCreate(BaseModel):
    name:str; email:EmailStr; password:str=Field(min_length=8); role:str="viewer"; firm_id:int|None=None
class UserUpdate(BaseModel):
    name:str|None=None; email:EmailStr|None=None; role:str|None=None; firm_id:int|None=None; password:str|None=Field(default=None,min_length=8)
class UserRead(BaseModel):
    user_id:int; name:str; email:EmailStr; role:str; firm_id:int|None; is_active:bool; model_config={"from_attributes":True}