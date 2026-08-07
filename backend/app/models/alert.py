from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AlertBase(SQLModel):
    budget_id: int = Field(foreign_key="budget.budget_id")
    type: str
    message: str
    created_at: str = Field(default_factory=_now_iso)


class Alert(AlertBase, table=True):
    __tablename__ = "alert"

    alert_id: Optional[int] = Field(default=None, primary_key=True)

    budget: Optional["Budget"] = Relationship(back_populates="alerts")


class AlertCreate(SQLModel):
    budget_id: int
    type: str
    message: str
    created_at: Optional[str] = None


class AlertRead(AlertBase):
    alert_id: int
