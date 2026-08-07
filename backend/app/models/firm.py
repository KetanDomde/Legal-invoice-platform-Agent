from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class FirmBase(SQLModel):
    name: str
    contact_email: Optional[str] = None
    status: str = "active"


class Firm(FirmBase, table=True):
    __tablename__ = "firm"

    firm_id: Optional[int] = Field(default=None, primary_key=True)

    matters: List["Matter"] = Relationship(back_populates="firm")
    users: List["User"] = Relationship(back_populates="firm")

    # SECONDARY relationship: Firm -> Invoice, derived through Matter.
    # No direct firm_id FK exists on invoice; Matter acts as the join table,
    # mirroring the Tag/InvoiceTagLink `secondary=` pattern. viewonly=True
    # because this path has no independent existence — it's just Matter's FK.
    invoices: List["Invoice"] = Relationship(
        sa_relationship_kwargs={
            "secondary": "matter",
            "primaryjoin": "Firm.firm_id==Matter.firm_id",
            "secondaryjoin": "Matter.matter_id==Invoice.matter_id",
            "viewonly": True,
        }
    )


class FirmCreate(FirmBase):
    pass


class FirmUpdate(SQLModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    status: Optional[str] = None


class FirmRead(FirmBase):
    firm_id: int
