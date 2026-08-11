from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.security import ADMIN, EDITOR, require_role
from app.database.database import get_db
from app.models import AuditLog, User
from app.schemas.audit import AuditLogRead


router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("/", response_model=list[AuditLogRead])
def list_audit_logs(
    invoice_id: int | None = None,
    user_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    query = db.query(AuditLog)
    if invoice_id is not None:
        query = query.filter(AuditLog.invoice_id == invoice_id)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if current_user.firm_id is not None:
        query = query.join(AuditLog.invoice, isouter=True).filter(
            (AuditLog.invoice_id.is_(None)) | (AuditLog.invoice.has(firm_id=current_user.firm_id))
        )
    return query.order_by(AuditLog.audit_id.desc()).offset(offset).limit(limit).all()


@router.get("/{log_id}", response_model=AuditLogRead)
def get_audit_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    log = db.get(AuditLog, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Audit log not found")
    if current_user.firm_id is not None and log.invoice is not None and log.invoice.firm_id != current_user.firm_id:
        raise HTTPException(status_code=403, detail="Permission denied")
    return log
