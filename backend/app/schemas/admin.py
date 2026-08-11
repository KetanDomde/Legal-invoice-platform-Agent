from pydantic import BaseModel, EmailStr, Field


class CreateUserRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    role: str
    firm_id: int | None = None


class ChangeRoleRequest(BaseModel):
    role: str


class UserAdminResponse(BaseModel):
    user_id: int
    name: str
    email: EmailStr
    role: str
    firm_id: int | None
    is_active: bool

    model_config = {"from_attributes": True}
