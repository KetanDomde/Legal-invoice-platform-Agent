from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class LineItemBase(SQLModel):
    invoice_id: int = Field(foreign_key="invoice.invoice_id")
    timekeeper: Optional[str] = None
    hours: Optional[float] = None
    rate: Optional[float] = None
    amount: float


class LineItem(LineItemBase, table=True):
    __tablename__ = "line_item"

    line_item_id: Optional[int] = Field(default=None, primary_key=True)

    invoice: Optional["Invoice"] = Relationship(back_populates="line_items")


class LineItemCreate(LineItemBase):
    pass


class LineItemUpdate(SQLModel):
    timekeeper: Optional[str] = None
    hours: Optional[float] = None
    rate: Optional[float] = None
    amount: Optional[float] = None


class LineItemRead(LineItemBase):
    line_item_id: int
