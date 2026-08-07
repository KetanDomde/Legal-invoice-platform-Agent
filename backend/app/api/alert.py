from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database.database_async import get_session
from app.models import Alert, AlertCreate, AlertRead, Budget

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.post("/", response_model=AlertRead, status_code=status.HTTP_201_CREATED)
async def create_alert(alert_in: AlertCreate, session: AsyncSession = Depends(get_session)):
    if not await session.get(Budget, alert_in.budget_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "budget_id does not exist")
    data = alert_in.model_dump(exclude_unset=True, exclude_none=True)
    alert = Alert(**data)
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert


@router.get("/", response_model=List[AlertRead])
async def list_alerts(
    budget_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    query = select(Alert)
    if budget_id is not None:
        query = query.where(Alert.budget_id == budget_id)
    result = await session.exec(query.offset(offset).limit(limit))
    return result.all()


@router.get("/{alert_id}", response_model=AlertRead)
async def get_alert(alert_id: int, session: AsyncSession = Depends(get_session)):
    alert = await session.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    return alert


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(alert_id: int, session: AsyncSession = Depends(get_session)):
    alert = await session.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    await session.delete(alert)
    await session.commit()
