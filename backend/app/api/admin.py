from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import ADMIN, require_role
from app.database.database import get_db
from app.models import User
from app.schemas.admin import ChangeRoleRequest, CreateUserRequest, UserAdminResponse
from app.services.users import change_user_role, create_user, deactivate_user


router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/users", response_model=UserAdminResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    try:
        return create_user(
            db,
            actor=current_user,
            name=request.name,
            email=request.email,
            password=request.password,
            role=request.role,
            firm_id=request.firm_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/users/{user_id}/deactivate", response_model=UserAdminResponse)
def admin_deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    try:
        return deactivate_user(db, actor=current_user, target_user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/users/{user_id}/role", response_model=UserAdminResponse)
def admin_change_role(
    user_id: int,
    request: ChangeRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    try:
        return change_user_role(
            db,
            actor=current_user,
            target_user_id=user_id,
            new_role=request.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
