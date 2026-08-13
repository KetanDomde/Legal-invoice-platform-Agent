from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def create_audit_log(
    db: Session,
    action: str,
    user_id: int | None = None,
    invoice_id: int | None = None,
    notes: str | None = None,
):
    audit = AuditLog(
        user_id=user_id,
        invoice_id=invoice_id,
        action=action,
        notes=notes,
    )

    db.add(audit)
    db.commit()
    db.refresh(audit)

    return audit