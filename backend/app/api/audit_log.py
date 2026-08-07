from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database.database_async import get_session
from app.models import AuditLog, AuditLogCreate, AuditLogRead, Invoice, User

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.post("/", response_model=AuditLogRead, status_code=status.HTTP_201_CREATED)
async def create_audit_log(log_in: AuditLogCreate, session: AsyncSession = Depends(get_session)):
    if log_in.invoice_id is not None and not await session.get(Invoice, log_in.invoice_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invoice_id does not exist")
    if log_in.user_id is not None and not await session.get(User, log_in.user_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id does not exist")
    data = log_in.model_dump(exclude_unset=True, exclude_none=True)
    log = AuditLog(**data)
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


@router.get("/", response_model=List[AuditLogRead])
async def list_audit_logs(
    invoice_id: int | None = None,
    user_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    query = select(AuditLog)
    if invoice_id is not None:
        query = query.where(AuditLog.invoice_id == invoice_id)
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
    result = await session.exec(query.offset(offset).limit(limit))
    return result.all()


@router.get("/{log_id}", response_model=AuditLogRead)
async def get_audit_log(log_id: int, session: AsyncSession = Depends(get_session)):
    log = await session.get(AuditLog, log_id)
    if not log:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit log not found")
    return log


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audit_log(log_id: int, session: AsyncSession = Depends(get_session)):
    # Audit logs are typically immutable; delete exposed only for admin cleanup.
    log = await session.get(AuditLog, log_id)
    if not log:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit log not found")
    await session.delete(log)
    await session.commit()
