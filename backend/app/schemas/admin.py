from pydantic import BaseModel, EmailStr

class CreateUserRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str
    firm_id: int | None = None

class ChangeRoleRequest(BaseModel):
    role: str

class UserAdminResponse(BaseModel):
    user_id: int
    name: str
    email: str
    role: str
    firm_id: int | None
    is_active: bool

    class Config:
        from_attributes = True