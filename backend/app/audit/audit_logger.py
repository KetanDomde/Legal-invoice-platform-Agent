from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.logger_config import request_id_ctx


def create_audit_log(
    db: Session,
    action: str,
    user_id: int,
    invoice_id: int | None = None,
    notes: str | None = None,
    request_id: str | None = None,
):
    """
    Create an audit log entry. `user_id` is required and must be an integer.
    Use `-1` to represent system actions.
    If `request_id` is not provided, the current `request_id` contextvar is used
    when available to persist end-to-end tracing information.
    """
    if user_id is None:
        raise ValueError("user_id is required for audit logs; use -1 for system actions")

    if request_id is None:
        # Use contextvar if middleware set it
        try:
            request_id = request_id_ctx.get()
        except Exception:
            request_id = None

    audit = AuditLog(
        user_id=user_id,
        invoice_id=invoice_id,
        action=action,
        notes=notes,
        request_id=request_id,
    )

    db.add(audit)
    db.commit()
    db.refresh(audit)

    return audit