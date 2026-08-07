from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class UserBase(SQLModel):
    name: str
    email: str = Field(unique=True, index=True)
    role: str = "viewer"  # admin | editor | viewer
    firm_id: Optional[int] = Field(default=None, foreign_key="firm.firm_id")


class User(UserBase, table=True):
    __tablename__ = "user"

    user_id: Optional[int] = Field(default=None, primary_key=True)
    password_hash: str

    firm: Optional["Firm"] = Relationship(back_populates="users")
    audit_logs: List["AuditLog"] = Relationship(back_populates="user")


class UserCreate(UserBase):
    password: str  # plaintext in, hashed before storage — never returned


class UserUpdate(SQLModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    firm_id: Optional[int] = None
    password: Optional[str] = None


class UserRead(UserBase):
    user_id: int
