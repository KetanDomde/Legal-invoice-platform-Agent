from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
)

from app.auth.auth import authenticate_user

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):

    result = authenticate_user(
        db,
        request.email,
        request.password,
    )

    if result is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    return {
        "access_token": result["access_token"],
        "token_type": "bearer",
    }