from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.auth import authenticate_user
from app.database.crud import write_audit_log
from app.database.session import get_db

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    result = authenticate_user(db, payload.email, payload.password)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    write_audit_log(db, "login", user_id=result["user"].user_id)
    return {
        "access_token": result["access_token"],
        "token_type": result["token_type"],
        "role": result["user"].role,
        "user_id": result["user"].user_id,
    }
