from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth.security import ADMIN, EDITOR, require_role
from app.database.database import get_db
from app.models import AuditLog, User
from app.schemas.audit import AuditLogRead


router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("/", response_model=list[AuditLogRead])
def list_audit_logs(
    invoice_id: int | None = None,
    user_id: int | None = None,
    filter: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    """
    List audit logs. Backwards-compatible invoice_id and user_id filters remain.
    A free-form `filter` string is supported for simple expressions such as:
      "notes ilike 'INV291-NS' and created_at >= '2026-08-20T05:27:41'"

    Supported ops: ilike, like, =, !=, >=, <=, >, <
    Supported fields: notes, action, invoice_id, user_id, user.name, created_at (or timestamp)
    This parser is intentionally minimal — keep expressions simple and admin-only.
    """
    query = db.query(AuditLog)
    # Join user if the filter references user fields
    join_user = False

    if invoice_id is not None:
        query = query.filter(AuditLog.invoice_id == invoice_id)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)

    if filter:
        import re
        from datetime import datetime

        # Split on case-insensitive ' and ' / ' or ' for now (only AND supported in parsing below)
        clauses = re.split(r"\s+and\s+", filter, flags=re.IGNORECASE)
        for clause in clauses:
            m = re.match(r"^\s*(?P<field>[a-zA-Z0-9_.]+)\s*(?P<op>ilike|like|!=|=|>=|<=|>|<)\s*'(?P<val>.*?)'\s*$", clause, flags=re.IGNORECASE)
            if m:
                field = m.group("field").lower()
                op = m.group("op").lower()
                val = m.group("val")

                if field in ("notes", "action"):
                    col = getattr(AuditLog, field)
                    if op == "ilike":
                        query = query.filter(col.ilike(val))
                    elif op == "like":
                        query = query.filter(col.like(val))
                    elif op == "=":
                        query = query.filter(col == val)
                    elif op == "!=":
                        query = query.filter(col != val)
                elif field in ("created_at", "timestamp"):
                    # parse ISO-ish datetimes
                    try:
                        dt = datetime.fromisoformat(val)
                    except Exception:
                        # try common alternative
                        dt = datetime.fromisoformat(val.replace(" ", "T"))
                    col = AuditLog.created_at
                    if op == ">=":
                        query = query.filter(col >= dt)
                    elif op == "<=":
                        query = query.filter(col <= dt)
                    elif op == ">":
                        query = query.filter(col > dt)
                    elif op == "<":
                        query = query.filter(col < dt)
                    elif op == "=":
                        query = query.filter(col == dt)
                elif field in ("invoice_id", "user_id"):
                    col = getattr(AuditLog, field)
                    # numeric comparison: try cast
                    try:
                        num = int(val)
                    except Exception:
                        continue
                    if op == "=":
                        query = query.filter(col == num)
                    elif op == "!=":
                        query = query.filter(col != num)
                    elif op == ">=":
                        query = query.filter(col >= num)
                    elif op == "<=":
                        query = query.filter(col <= num)
                    elif op == ">":
                        query = query.filter(col > num)
                    elif op == "<":
                        query = query.filter(col < num)
                elif field.startswith("user"):
                    # support `user.name` or `user` (name)
                    join_user = True
                    # map to User.name
                    from app.models import User as UserModel
                    col = UserModel.name
                    if op == "ilike":
                        query = query.filter(col.ilike(val))
                    elif op == "like":
                        query = query.filter(col.like(val))
                    elif op == "=":
                        query = query.filter(col == val)
                    elif op == "!=":
                        query = query.filter(col != val)
                else:
                    # unknown field — skip
                    continue
            else:
                # try simple numeric equality like: invoice_id=123 (no quotes)
                m2 = re.match(r"^\s*(?P<field>[a-zA-Z0-9_.]+)\s*(?P<op>=|!=|>=|<=|>|<)\s*(?P<val>[-0-9]+)\s*$", clause)
                if m2:
                    field = m2.group("field").lower()
                    op = m2.group("op")
                    val = int(m2.group("val"))
                    if field in ("invoice_id", "user_id"):
                        col = getattr(AuditLog, field)
                        if op == "=":
                            query = query.filter(col == val)
                        elif op == "!=":
                            query = query.filter(col != val)
                        elif op == ">=":
                            query = query.filter(col >= val)
                        elif op == "<=":
                            query = query.filter(col <= val)
                        elif op == ">":
                            query = query.filter(col > val)
                        elif op == "<":
                            query = query.filter(col < val)

    if current_user.firm_id is not None:
        query = query.join(AuditLog.invoice, isouter=True).filter(
            (AuditLog.invoice_id.is_(None)) | (AuditLog.invoice.has(firm_id=current_user.firm_id))
        )

    if join_user:
        # ensure user relationship is loaded for response `user_name` property
        query = query.options(joinedload(AuditLog.user))

    return query.order_by(AuditLog.audit_id.desc()).limit(limit).all()


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
