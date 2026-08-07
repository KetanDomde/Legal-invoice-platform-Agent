from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database.database_async import get_session
from app.models import Firm, Matter, MatterCreate, MatterRead, MatterUpdate

router = APIRouter(prefix="/matters", tags=["Matters"])


@router.post("/", response_model=MatterRead, status_code=status.HTTP_201_CREATED)
async def create_matter(matter_in: MatterCreate, session: AsyncSession = Depends(get_session)):
    if not await session.get(Firm, matter_in.firm_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "firm_id does not exist")
    matter = Matter.model_validate(matter_in)
    session.add(matter)
    await session.commit()
    await session.refresh(matter)
    return matter


@router.get("/", response_model=List[MatterRead])
async def list_matters(
    firm_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    query = select(Matter)
    if firm_id is not None:
        query = query.where(Matter.firm_id == firm_id)
    result = await session.exec(query.offset(offset).limit(limit))
    return result.all()


@router.get("/{matter_id}", response_model=MatterRead)
async def get_matter(matter_id: int, session: AsyncSession = Depends(get_session)):
    matter = await session.get(Matter, matter_id)
    if not matter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Matter not found")
    return matter


@router.patch("/{matter_id}", response_model=MatterRead)
async def update_matter(
    matter_id: int, matter_in: MatterUpdate, session: AsyncSession = Depends(get_session)
):
    matter = await session.get(Matter, matter_id)
    if not matter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Matter not found")
    for key, value in matter_in.model_dump(exclude_unset=True).items():
        setattr(matter, key, value)
    session.add(matter)
    await session.commit()
    await session.refresh(matter)
    return matter


@router.delete("/{matter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_matter(matter_id: int, session: AsyncSession = Depends(get_session)):
    matter = await session.get(Matter, matter_id)
    if not matter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Matter not found")
    await session.delete(matter)
    await session.commit()
