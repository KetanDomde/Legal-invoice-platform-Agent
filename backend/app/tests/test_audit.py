from app.models.audit_log import AuditLog
def test_audit_log_created(
    db,
):
    from app.audit.audit_logger import (
        create_audit_log,
    )
    audit = create_audit_log(
        db=db,
        action="approved",
        user_id=10,
        invoice_id=20,
        notes=(
            "Status changed from "
            "'pending_review' to 'approved'."
        ),
    )

    assert audit.audit_id is not None
    assert audit.user_id == 10
    assert audit.invoice_id == 20
    assert audit.action == "approved"

def test_system_audit_can_have_no_user(
    db,
):

    from app.audit.audit_logger import (
        create_audit_log,
    )

    audit = create_audit_log(
        db=db,
        action="auto_approved",
        user_id=-1,
        invoice_id=30,
        notes="All validation checks passed.",
    )

    assert audit.user_id == -1
    assert audit.invoice_id == 30