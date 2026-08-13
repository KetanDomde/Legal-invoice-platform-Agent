from pymupdf import message
from sqlalchemy.orm import Session

from app.validation.budget_validator import (
    validate_budget,
)

from app.validation.duplicate_detector import (
    check_duplicate,
)


def validate_invoice(
    db: Session,
    matter_id: int,
    firm_id: int,
    invoice_no: str,
    total_amount: float,
    invoice_id: int | None = None,
) -> dict:
    """
    Run all invoice validation checks.

    Checks:
        1. Budget
        2. Duplicate
    """

    reasons = []

    # -----------------------------
    # Budget validation
    # -----------------------------

    budget_result = validate_budget(
        db=db,
        matter_id=matter_id,
        invoice_amount=total_amount,
    )

    if not budget_result["budget_ok"]:
        reasons.append(
            budget_result["reason"]
        )

    # -----------------------------
    # Duplicate validation
    # -----------------------------

    duplicate_result = check_duplicate(
        db=db,
        firm_id=firm_id,
        invoice_no=invoice_no,
        total_amount=total_amount,
        exclude_invoice_id=invoice_id,
    )

    if duplicate_result["duplicate"]:
        reasons.append(
            duplicate_result["reason"]
        )

    # -----------------------------
    # Overall validation
    # -----------------------------

    validation_passed = (
        budget_result["budget_ok"]
        and not duplicate_result["duplicate"]
    )

    return {
        "validation_passed": validation_passed,

        "budget_ok": budget_result[
            "budget_ok"
        ],

        "remaining_budget": budget_result[
            "remaining_budget"
        ],

        "duplicate": duplicate_result[
            "duplicate"
        ],

        "duplicate_invoice_id": duplicate_result[
            "duplicate_invoice_id"
        ],

        "reasons": reasons,
    }
    
class ValidationResult:

    def __init__(
        self,
        budget_valid: bool | None = None,
        duplicate_flag: bool = False,
        validation_status: str = "valid",
        validation_message: str | None = None,
    ):
        self.budget_valid = budget_valid
        self.duplicate_flag = duplicate_flag
        self.validation_status = validation_status
        self.validation_message = validation_message
        

        
        return ValidationResult(
        budget_valid=budget_valid,
        duplicate_flag=duplicate_flag,
        validation_status=validation_status,
        validation_message=message,
        )
        
     
     
     
## code chnage from here 
 
from sqlalchemy.orm import Session

from app.models.invoice import Invoice

from app.validation.router import (
    route_invoice,
)

from app.audit.audit_logger import (
    create_audit_log,
)
  


def validate_and_route_invoice(
    db: Session,
    invoice: Invoice,
    budget_valid: bool | None,
    duplicate_flag: bool,
):

    result = route_invoice(
        confidence_score=invoice.confidence_score,
        budget_valid=budget_valid,
        duplicate_flag=duplicate_flag,
    )

    # --------------------------------------------------
    # Store validation result
    # --------------------------------------------------

    invoice.budget_valid = budget_valid

    invoice.duplicate_flag = duplicate_flag

    if result.decision == "auto_approved":

        invoice.validation_status = "passed"

        invoice.validation_message = (
            "All validation checks passed"
        )

        invoice.status = "approved"

        action = "auto_approved"

    else:

        invoice.validation_status = "failed"

        invoice.validation_message = (
            "; ".join(result.reasons)
        )

        invoice.status = "pending_review"

        action = "validated"

    db.add(invoice)

    db.commit()

    db.refresh(invoice)

    # --------------------------------------------------
    # Audit
    # --------------------------------------------------

    create_audit_log(
        db=db,
        action=action,
        user_id=None,
        invoice_id=invoice.invoice_id,
        notes="; ".join(result.reasons),
    )

    return result