from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user, require_role
from app.auth.roles import (
    ADMIN,
    EDITOR,
)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get("/me")
def current_user(
    user=Depends(get_current_user),
):

    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "firm_id": user.firm_id,
    }


@router.get("/admin")
def admin_only(
    user=Depends(
        require_role([ADMIN])
    ),
):

    return {
        "message": "Welcome Admin",
        "user": user.name,
    }


@router.get("/editor")
def editor_only(
    user=Depends(
        require_role(
            [ADMIN, EDITOR]
        )
    ),
):

    return {
        "message": "Editor Access",
        "user": user.name,
    }