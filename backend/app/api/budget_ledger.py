from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database.database_async import get_session
from app.models import Budget, BudgetLedger, BudgetLedgerCreate, BudgetLedgerRead, Invoice

router = APIRouter(prefix="/budget-ledger", tags=["Budget Ledger"])


@router.post("/", response_model=BudgetLedgerRead, status_code=status.HTTP_201_CREATED)
async def create_ledger_entry(
    entry_in: BudgetLedgerCreate, session: AsyncSession = Depends(get_session)
):
    if not await session.get(Budget, entry_in.budget_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "budget_id does not exist")
    if not await session.get(Invoice, entry_in.invoice_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invoice_id does not exist")
    data = entry_in.model_dump(exclude_unset=True, exclude_none=True)
    entry = BudgetLedger(**data)
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


@router.get("/", response_model=List[BudgetLedgerRead])
async def list_ledger_entries(
    budget_id: int | None = None,
    invoice_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    query = select(BudgetLedger)
    if budget_id is not None:
        query = query.where(BudgetLedger.budget_id == budget_id)
    if invoice_id is not None:
        query = query.where(BudgetLedger.invoice_id == invoice_id)
    result = await session.exec(query.offset(offset).limit(limit))
    return result.all()


@router.get("/{ledger_id}", response_model=BudgetLedgerRead)
async def get_ledger_entry(ledger_id: int, session: AsyncSession = Depends(get_session)):
    entry = await session.get(BudgetLedger, ledger_id)
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ledger entry not found")
    return entry


@router.delete("/{ledger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ledger_entry(ledger_id: int, session: AsyncSession = Depends(get_session)):
    # Ledger entries are append-only (no update route) — deletion only, for corrections.
    entry = await session.get(BudgetLedger, ledger_id)
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ledger entry not found")
    await session.delete(entry)
    await session.commit()
