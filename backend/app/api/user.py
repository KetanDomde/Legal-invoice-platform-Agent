from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database.database_async import get_session
from app.models import Firm, User, UserCreate, UserRead, UserUpdate
from app.core.security import hash_password

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, session: AsyncSession = Depends(get_session)):
    if user_in.firm_id is not None and not await session.get(Firm, user_in.firm_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "firm_id does not exist")
    existing = await session.exec(select(User).where(User.email == user_in.email))
    if existing.first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

    user = User(
        name=user_in.name,
        email=user_in.email,
        role=user_in.role,
        firm_id=user_in.firm_id,
        password_hash=hash_password(user_in.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/", response_model=List[UserRead])
async def list_users(
    firm_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    query = select(User)
    if firm_id is not None:
        query = query.where(User.firm_id == firm_id)
    result = await session.exec(query.offset(offset).limit(limit))
    return result.all()


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, session: AsyncSession = Depends(get_session)):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int, user_in: UserUpdate, session: AsyncSession = Depends(get_session)
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    data = user_in.model_dump(exclude_unset=True)
    if "password" in data:
        user.password_hash = hash_password(data.pop("password"))
    for key, value in data.items():
        setattr(user, key, value)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, session: AsyncSession = Depends(get_session)):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    await session.delete(user)
    await session.commit()
