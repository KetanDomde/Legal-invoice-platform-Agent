from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog

def create_audit_log(
    db: Session,
    action: str,
    user_id: int | None = None,
    invoice_id: int | None = None,
    notes: str | None = None,
):

    """
    Create an audit record for an invoice action.
    """
    
    audit = AuditLog(
        invoice_id=invoice_id,
        user_id=user_id,
        action=action,
        notes=notes,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    db.add(audit)
    db.commit()
    db.refresh(audit)

    return audit