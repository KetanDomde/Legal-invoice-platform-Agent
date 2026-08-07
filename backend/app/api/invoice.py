from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database.database_async import get_session
from app.models import Invoice, InvoiceCreate, InvoiceRead, InvoiceUpdate, Matter

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post("/", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
async def create_invoice(invoice_in: InvoiceCreate, session: AsyncSession = Depends(get_session)):
    if not await session.get(Matter, invoice_in.matter_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "matter_id does not exist")
    invoice = Invoice.model_validate(invoice_in)
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return invoice


@router.get("/", response_model=List[InvoiceRead])
async def list_invoices(
    matter_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    query = select(Invoice)
    if matter_id is not None:
        query = query.where(Invoice.matter_id == matter_id)
    result = await session.exec(query.offset(offset).limit(limit))
    return result.all()


@router.get("/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(invoice_id: int, session: AsyncSession = Depends(get_session)):
    invoice = await session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
    return invoice


@router.patch("/{invoice_id}", response_model=InvoiceRead)
async def update_invoice(
    invoice_id: int, invoice_in: InvoiceUpdate, session: AsyncSession = Depends(get_session)
):
    invoice = await session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
    for key, value in invoice_in.model_dump(exclude_unset=True).items():
        setattr(invoice, key, value)
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return invoice


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(invoice_id: int, session: AsyncSession = Depends(get_session)):
    invoice = await session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
    await session.delete(invoice)
    await session.commit()
