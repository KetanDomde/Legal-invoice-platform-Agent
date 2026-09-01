from datetime import date, datetime, timedelta
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.auth.security import ADMIN, EDITOR, require_role
from app.database.database import get_db
from app.models import AuditLog, Firm, Invoice, Matter, User
from app.schemas.audit import AuditLogPage, AuditLogRead


router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def _audit_context(db: Session, log: AuditLog) -> dict:
    """Resolve database IDs into names/numbers an administrator can understand.

    Audit rows can be invoice-centric, matter-centric, or budget-centric.  Older
    rows may not contain every ID, so resolve the most specific available path
    without fabricating missing historical information.
    """
    invoice = db.get(Invoice, log.invoice_id) if log.invoice_id is not None else None

    firm_id = getattr(log, "firm_id", None)
    matter_id = getattr(log, "matter_id", None)

    if invoice is not None:
        firm_id = firm_id if firm_id is not None else invoice.firm_id
        matter_id = matter_id if matter_id is not None else invoice.matter_id

    matter = db.get(Matter, matter_id) if matter_id is not None else None
    if matter is not None and firm_id is None:
        firm_id = matter.firm_id

    firm = db.get(Firm, firm_id) if firm_id is not None else None

    matter_no = getattr(matter, "matter_no", None) if matter is not None else None
    matter_name = getattr(matter, "name", None) if matter is not None else None
    if matter_no and matter_name:
        matter_label = f"{matter_no} — {matter_name}"
    else:
        matter_label = matter_no or matter_name

    return {
        "invoice_no": getattr(invoice, "invoice_no", None) if invoice is not None else None,
        "firm_name": getattr(firm, "name", None) if firm is not None else None,
        "matter_no": matter_no,
        "matter_name": matter_name,
        "matter_label": matter_label,
    }


def _serialize_log(db: Session, log: AuditLog) -> dict:
    context = _audit_context(db, log)
    return {
        "audit_id": log.audit_id,
        "invoice_id": log.invoice_id,
        "invoice_no": context["invoice_no"],
        "user_id": log.user_id,
        "user_name": log.user.name if getattr(log, "user", None) is not None else None,
        "action": log.action,
        "notes": log.notes,
        "request_id": log.request_id,
        "created_at": log.created_at,
        "firm_id": getattr(log, "firm_id", None),
        "firm_name": context["firm_name"],
        "matter_id": getattr(log, "matter_id", None),
        "matter_no": context["matter_no"],
        "matter_name": context["matter_name"],
        "matter_label": context["matter_label"],
        "budget_id": getattr(log, "budget_id", None),
        "previous_value": getattr(log, "previous_value", None),
        "adjustment_amount": getattr(log, "adjustment_amount", None),
        "new_value": getattr(log, "new_value", None),
        "reason": getattr(log, "reason", None),
        "confirmed": getattr(log, "confirmed", None),
    }


@router.get("/", response_model=list[AuditLogRead])
def list_audit_logs(
    invoice_id: int | None = None,
    user_id: int | None = None,
    filter: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    """List audit logs with business-readable firm, matter, and invoice context."""
    query = db.query(AuditLog).options(joinedload(AuditLog.user))

    if invoice_id is not None:
        query = query.filter(AuditLog.invoice_id == invoice_id)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)

    if filter:
        clauses = re.split(r"\s+and\s+", filter, flags=re.IGNORECASE)
        for clause in clauses:
            m = re.match(
                r"^\s*(?P<field>[a-zA-Z0-9_.]+)\s*"
                r"(?P<op>ilike|like|!=|=|>=|<=|>|<)\s*'(?P<val>.*?)'\s*$",
                clause,
                flags=re.IGNORECASE,
            )
            if not m:
                m2 = re.match(
                    r"^\s*(?P<field>[a-zA-Z0-9_.]+)\s*(?P<op>=|!=|>=|<=|>|<)\s*(?P<val>[-0-9]+)\s*$",
                    clause,
                )
                if not m2:
                    continue
                field, op, val = m2.group("field").lower(), m2.group("op"), m2.group("val")
            else:
                field, op, val = m.group("field").lower(), m.group("op").lower(), m.group("val")

            if field in {"notes", "action", "request_id"}:
                col = getattr(AuditLog, field)
                if op == "ilike":
                    query = query.filter(col.ilike(val))
                elif op == "like":
                    query = query.filter(col.like(val))
                elif op == "=":
                    query = query.filter(col == val)
                elif op == "!=":
                    query = query.filter(col != val)
            elif field in {"created_at", "timestamp"}:
                try:
                    dt = datetime.fromisoformat(str(val).replace(" ", "T"))
                except ValueError:
                    continue
                col = AuditLog.created_at
                query = {
                    ">=": query.filter(col >= dt), "<=": query.filter(col <= dt),
                    ">": query.filter(col > dt), "<": query.filter(col < dt),
                    "=": query.filter(col == dt),
                }.get(op, query)
            elif field in {"invoice_id", "user_id", "firm_id", "matter_id", "budget_id"}:
                try:
                    num = int(val)
                except (TypeError, ValueError):
                    continue
                col = getattr(AuditLog, field)
                query = {
                    "=": query.filter(col == num), "!=": query.filter(col != num),
                    ">=": query.filter(col >= num), "<=": query.filter(col <= num),
                    ">": query.filter(col > num), "<": query.filter(col < num),
                }.get(op, query)
            elif field in {"invoice_no", "firm_name", "matter_no", "matter_name"}:
                # Business filters are resolved through the domain entities.
                if field == "invoice_no":
                    query = query.join(Invoice, AuditLog.invoice_id == Invoice.invoice_id)
                    col = Invoice.invoice_no
                elif field == "firm_name":
                    query = query.outerjoin(Firm, AuditLog.firm_id == Firm.firm_id)
                    col = Firm.name
                else:
                    query = query.outerjoin(Matter, AuditLog.matter_id == Matter.matter_id)
                    col = Matter.matter_no if field == "matter_no" else Matter.name
                if op == "ilike":
                    query = query.filter(col.ilike(val))
                elif op == "like":
                    query = query.filter(col.like(val))
                elif op == "=":
                    query = query.filter(col == val)
                elif op == "!=":
                    query = query.filter(col != val)

    # Firm-scoped users can only see rows belonging to their firm. For older
    # generic rows with no firm context, retain the existing invoice fallback.
    if current_user.firm_id is not None:
        query = query.outerjoin(Invoice, AuditLog.invoice_id == Invoice.invoice_id).filter(
            (getattr(AuditLog, "firm_id") == current_user.firm_id)
            | ((getattr(AuditLog, "firm_id").is_(None)) & (Invoice.firm_id == current_user.firm_id))
        )

    rows = query.order_by(AuditLog.audit_id.desc()).limit(limit).all()
    return [_serialize_log(db, row) for row in rows]


@router.get("/page", response_model=AuditLogPage)
def list_audit_logs_page(
    invoice_no: str | None = None,
    firm_name: str | None = None,
    matter_no: str | None = None,
    matter_name: str | None = None,
    request_id: str | None = None,
    action: str | None = None,
    user_name: str | None = None,
    general: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    offset: int = 0,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    """Paginated audit history with business-friendly filters.

    This is additive: the legacy list endpoint remains unchanged for existing
    callers. Results are always newest first so page 1 is the latest activity.
    """
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    query = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.user))
        .outerjoin(Invoice, AuditLog.invoice_id == Invoice.invoice_id)
        .outerjoin(
            Firm,
            or_(
                AuditLog.firm_id == Firm.firm_id,
                and_(AuditLog.firm_id.is_(None), Invoice.firm_id == Firm.firm_id),
            ),
        )
        .outerjoin(
            Matter,
            or_(
                AuditLog.matter_id == Matter.matter_id,
                and_(AuditLog.matter_id.is_(None), Invoice.matter_id == Matter.matter_id),
            ),
        )
        .outerjoin(User, AuditLog.user_id == User.user_id)
    )

    if invoice_no:
        query = query.filter(Invoice.invoice_no.ilike(f"%{invoice_no.strip()}%"))
    if firm_name:
        query = query.filter(Firm.name.ilike(f"%{firm_name.strip()}%"))
    if matter_no:
        query = query.filter(Matter.matter_no.ilike(f"%{matter_no.strip()}%"))
    if matter_name:
        query = query.filter(Matter.name.ilike(f"%{matter_name.strip()}%"))
    if request_id:
        query = query.filter(AuditLog.request_id.ilike(f"%{request_id.strip()}%"))
    if action:
        query = query.filter(AuditLog.action == action)
    if user_name:
        if user_name == "System":
            query = query.filter(AuditLog.user_id == -1)
        else:
            query = query.filter(User.name == user_name)
    if start_date:
        query = query.filter(AuditLog.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(
            AuditLog.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time())
        )
    if general:
        term = f"%{general.strip()}%"
        query = query.filter(or_(
            AuditLog.action.ilike(term),
            AuditLog.notes.ilike(term),
            AuditLog.request_id.ilike(term),
            Invoice.invoice_no.ilike(term),
            Firm.name.ilike(term),
            Matter.matter_no.ilike(term),
            Matter.name.ilike(term),
            User.name.ilike(term),
        ))

    if current_user.firm_id is not None:
        query = query.filter(Firm.firm_id == current_user.firm_id)

    total = query.order_by(None).count()
    rows = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.audit_id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [_serialize_log(db, row) for row in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{log_id}", response_model=AuditLogRead)
def get_audit_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    log = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.user))
        .filter(AuditLog.audit_id == log_id)
        .first()
    )
    if log is None:
        raise HTTPException(status_code=404, detail="Audit log not found")

    if current_user.firm_id is not None:
        context = _audit_context(db, log)
        if context["firm_name"] is None:
            raise HTTPException(status_code=403, detail="Permission denied")
        firm_id = getattr(log, "firm_id", None)
        if firm_id is None and log.invoice is not None:
            firm_id = log.invoice.firm_id
        if firm_id != current_user.firm_id:
            raise HTTPException(status_code=403, detail="Permission denied")

    return _serialize_log(db, log)