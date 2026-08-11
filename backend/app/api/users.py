from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import ADMIN, EDITOR, get_current_user, require_role, hash_password
from app.database.database import get_db
from app.models import Firm, User
from app.schemas.billing import UserCreate, UserRead, UserUpdate


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/", response_model=list[UserRead])
def list_users(
    firm_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    if current_user.firm_id is not None:
        firm_id = current_user.firm_id
    query = db.query(User)
    if firm_id is not None:
        query = query.filter(User.firm_id == firm_id)
    return query.order_by(User.user_id.asc()).offset(0).limit(100).all()


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    request: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    if current_user.firm_id is not None and request.firm_id != current_user.firm_id:
        raise HTTPException(status_code=403, detail="Cannot create a user outside your own firm.")
    if request.firm_id is not None and db.get(Firm, request.firm_id) is None:
        raise HTTPException(status_code=400, detail="firm_id does not exist")
    if db.query(User).filter(User.email == request.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=request.name,
        email=request.email,
        password_hash=hash_password(request.password),
        role=request.role,
        firm_id=request.firm_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    request: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.firm_id is not None and user.firm_id != current_user.firm_id:
        raise HTTPException(status_code=403, detail="Cannot manage a user outside your own firm.")

    data = request.model_dump(exclude_unset=True)
    if "password" in data:
        user.password_hash = hash_password(data.pop("password"))
    if "email" in data and data["email"] != user.email:
        if db.query(User).filter(User.email == data["email"]).first():
            raise HTTPException(status_code=400, detail="Email already registered")
    if "firm_id" in data and current_user.firm_id is not None and data["firm_id"] != current_user.firm_id:
        raise HTTPException(status_code=403, detail="Cannot move a user outside your own firm.")
    for key, value in data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN])),
):
    if user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="An Admin cannot delete their own account.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.firm_id is not None and user.firm_id != current_user.firm_id:
        raise HTTPException(status_code=403, detail="Cannot manage a user outside your own firm.")
    db.delete(user)
    db.commit()
