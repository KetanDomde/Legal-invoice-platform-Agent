from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class MatterBase(SQLModel):
    firm_id: int = Field(foreign_key="firm.firm_id")
    name: str
    owner: str
    status: str = "open"


class Matter(MatterBase, table=True):
    __tablename__ = "matter"

    matter_id: Optional[int] = Field(default=None, primary_key=True)

    firm: Optional["Firm"] = Relationship(back_populates="matters")
    budget: Optional["Budget"] = Relationship(
        back_populates="matter", sa_relationship_kwargs={"uselist": False}
    )
    invoices: List["Invoice"] = Relationship(back_populates="matter")


class MatterCreate(MatterBase):
    pass


class MatterUpdate(SQLModel):
    firm_id: Optional[int] = None
    name: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None


class MatterRead(MatterBase):
    matter_id: int
