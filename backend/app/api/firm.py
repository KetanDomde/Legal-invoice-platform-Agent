from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database.database_async import get_session
from app.models import Firm, FirmCreate, FirmRead, FirmUpdate

router = APIRouter(prefix="/firms", tags=["Firms"])


@router.post("/", response_model=FirmRead, status_code=status.HTTP_201_CREATED)
async def create_firm(firm_in: FirmCreate, session: AsyncSession = Depends(get_session)):
    firm = Firm.model_validate(firm_in)
    session.add(firm)
    await session.commit()
    await session.refresh(firm)
    return firm


@router.get("/", response_model=List[FirmRead])
async def list_firms(
    offset: int = 0, limit: int = 100, session: AsyncSession = Depends(get_session)
):
    result = await session.exec(select(Firm).offset(offset).limit(limit))
    return result.all()


@router.get("/{firm_id}", response_model=FirmRead)
async def get_firm(firm_id: int, session: AsyncSession = Depends(get_session)):
    firm = await session.get(Firm, firm_id)
    if not firm:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Firm not found")
    return firm


@router.patch("/{firm_id}", response_model=FirmRead)
async def update_firm(
    firm_id: int, firm_in: FirmUpdate, session: AsyncSession = Depends(get_session)
):
    firm = await session.get(Firm, firm_id)
    if not firm:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Firm not found")
    for key, value in firm_in.model_dump(exclude_unset=True).items():
        setattr(firm, key, value)
    session.add(firm)
    await session.commit()
    await session.refresh(firm)
    return firm


@router.delete("/{firm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_firm(firm_id: int, session: AsyncSession = Depends(get_session)):
    firm = await session.get(Firm, firm_id)
    if not firm:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Firm not found")
    await session.delete(firm)
    await session.commit()
