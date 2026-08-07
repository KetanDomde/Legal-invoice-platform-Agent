from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database.database_async import get_session
from app.models import Invoice, LineItem, LineItemCreate, LineItemRead, LineItemUpdate

router = APIRouter(prefix="/line-items", tags=["Line Items"])


@router.post("/", response_model=LineItemRead, status_code=status.HTTP_201_CREATED)
async def create_line_item(
    line_item_in: LineItemCreate, session: AsyncSession = Depends(get_session)
):
    if not await session.get(Invoice, line_item_in.invoice_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invoice_id does not exist")
    line_item = LineItem.model_validate(line_item_in)
    session.add(line_item)
    await session.commit()
    await session.refresh(line_item)
    return line_item


@router.get("/", response_model=List[LineItemRead])
async def list_line_items(
    invoice_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    query = select(LineItem)
    if invoice_id is not None:
        query = query.where(LineItem.invoice_id == invoice_id)
    result = await session.exec(query.offset(offset).limit(limit))
    return result.all()


@router.get("/{line_item_id}", response_model=LineItemRead)
async def get_line_item(line_item_id: int, session: AsyncSession = Depends(get_session)):
    line_item = await session.get(LineItem, line_item_id)
    if not line_item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Line item not found")
    return line_item


@router.patch("/{line_item_id}", response_model=LineItemRead)
async def update_line_item(
    line_item_id: int,
    line_item_in: LineItemUpdate,
    session: AsyncSession = Depends(get_session),
):
    line_item = await session.get(LineItem, line_item_id)
    if not line_item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Line item not found")
    for key, value in line_item_in.model_dump(exclude_unset=True).items():
        setattr(line_item, key, value)
    session.add(line_item)
    await session.commit()
    await session.refresh(line_item)
    return line_item


@router.delete("/{line_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_line_item(line_item_id: int, session: AsyncSession = Depends(get_session)):
    line_item = await session.get(LineItem, line_item_id)
    if not line_item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Line item not found")
    await session.delete(line_item)
    await session.commit()
