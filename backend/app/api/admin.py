from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.orm import Session
from app.database.database import get_db
from app.auth.dependencies import (
    require_role,
)
from app.auth.roles import ADMIN
from app.models.user import User

from app.schemas.admin import (
    CreateUserRequest,
    ChangeRoleRequest,
    UserAdminResponse,
)

from app.services.user_service import (
    create_user,
    deactivate_user,
    change_user_role,
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


# ============================================================
# CREATE USER
# ============================================================

@router.post(
    "/users",
    response_model=UserAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_user(
    request: CreateUserRequest,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role([ADMIN])
    ),
):
    """
    Create a new user.

    Admin only.
    """

    try:

        return create_user(
            db=db,
            name=request.name,
            email=request.email,
            password=request.password,
            role=request.role,
            firm_id=request.firm_id,
            actor_user_id=current_user.user_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ============================================================
# DEACTIVATE USER
# ============================================================

@router.patch(
    "/users/{user_id}/deactivate",
    response_model=UserAdminResponse,
)
def deactivate_existing_user(
    user_id: int,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role([ADMIN])
    ),
):
    """
    Deactivate another user.

    Admin only.
    """

    try:

        return deactivate_user(
            db=db,
            target_user_id=user_id,
            actor_user_id=current_user.user_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ============================================================
# CHANGE ROLE
# ============================================================

@router.patch(
    "/users/{user_id}/role",
    response_model=UserAdminResponse,
)
def change_existing_user_role(
    user_id: int,

    request: ChangeRoleRequest,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role([ADMIN])
    ),
):
    """
    Change another user's role.

    Admin only.
    """

    try:

        return change_user_role(
            db=db,
            target_user_id=user_id,
            new_role=request.role,
            actor_user_id=current_user.user_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )