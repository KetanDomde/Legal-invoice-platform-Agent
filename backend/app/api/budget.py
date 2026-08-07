from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database.database_async import get_session
from app.models import Budget, BudgetCreate, BudgetRead, BudgetUpdate, Matter

router = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.post("/", response_model=BudgetRead, status_code=status.HTTP_201_CREATED)
async def create_budget(budget_in: BudgetCreate, session: AsyncSession = Depends(get_session)):
    if not await session.get(Matter, budget_in.matter_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "matter_id does not exist")
    existing = await session.exec(select(Budget).where(Budget.matter_id == budget_in.matter_id))
    if existing.first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Matter already has a budget")
    budget = Budget.model_validate(budget_in)
    session.add(budget)
    await session.commit()
    await session.refresh(budget)
    return budget


@router.get("/", response_model=List[BudgetRead])
async def list_budgets(
    offset: int = 0, limit: int = 100, session: AsyncSession = Depends(get_session)
):
    result = await session.exec(select(Budget).offset(offset).limit(limit))
    return result.all()


@router.get("/{budget_id}", response_model=BudgetRead)
async def get_budget(budget_id: int, session: AsyncSession = Depends(get_session)):
    budget = await session.get(Budget, budget_id)
    if not budget:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Budget not found")
    return budget


@router.patch("/{budget_id}", response_model=BudgetRead)
async def update_budget(
    budget_id: int, budget_in: BudgetUpdate, session: AsyncSession = Depends(get_session)
):
    budget = await session.get(Budget, budget_id)
    if not budget:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Budget not found")
    for key, value in budget_in.model_dump(exclude_unset=True).items():
        setattr(budget, key, value)
    session.add(budget)
    await session.commit()
    await session.refresh(budget)
    return budget


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(budget_id: int, session: AsyncSession = Depends(get_session)):
    budget = await session.get(Budget, budget_id)
    if not budget:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Budget not found")
    await session.delete(budget)
    await session.commit()
