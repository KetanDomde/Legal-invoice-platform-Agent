from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.orm import Session

from app.database.database import get_db

from app.auth.dependencies import (
    get_current_user,
)

from app.models.user import User

from app.schemas.validation import (
    ValidationRequest,
    ValidationResponse,
)
from app.models.invoice import Invoice


from app.validation.validation_service import (
    validate_and_route_invoice,
)

from app.validation.validation_service import (
    validate_invoice,
)

from app.validation.router import (
    make_decision,
)

from app.services.invoice_status_service import (
    update_invoice_status_from_validation,
)
from app.auth.dependencies import require_role
from app.auth.roles import ADMIN, EDITOR

router = APIRouter(
    prefix="/validation",
    tags=["Validation"],
)


@router.post(
    "/validate",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
)
def validate(
    request: ValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])
    ),
):
    """
    Validate an invoice and determine
    whether it should be auto-approved
    or sent for human review.

    Validation checks:

    1. Budget validation
    2. Duplicate invoice detection
    3. Confidence threshold
    4. Auto-approve / human-review routing
    5. Invoice status update
    """

    # =========================================================
    # 1. FIRM-LEVEL SECURITY
    # =========================================================

    # Admin users without a firm_id can access
    # all firms.

    if (
        current_user.firm_id is not None
        and current_user.firm_id != request.firm_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not authorized to "
                "access invoices belonging to "
                "another firm."
            ),
        )

    # =========================================================
    # 2. RUN VALIDATION
    # =========================================================

    try:

        validation_result = validate_invoice(
            db=db,
            matter_id=request.matter_id,
            firm_id=request.firm_id,
            invoice_no=request.invoice_no,
            total_amount=request.total_amount,
            invoice_id=request.invoice_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "An unexpected error occurred "
                "during invoice validation."
            ),
        )

    # =========================================================
    # 3. MAKE ROUTING DECISION
    # =========================================================

    try:

        decision = make_decision(
            confidence_score=request.confidence_score,
            validation=validation_result,
        )

    except Exception:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Unable to determine "
                "invoice routing decision."
            ),
        )

    # =========================================================
    # 4. UPDATE INVOICE STATUS
    # =========================================================

    if request.invoice_id is not None:

        try:

            update_invoice_status_from_validation(
                db=db,
                invoice_id=request.invoice_id,
                decision=decision["decision"],
            )

        except ValueError as exc:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            )

        except Exception:

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Validation completed, but "
                    "invoice status could not be updated."
                ),
            )

    # =========================================================
    # 5. BUILD RESPONSE
    # =========================================================

    response = {
        "validation_passed": validation_result[
            "validation_passed"
        ],

        "budget_ok": validation_result[
            "budget_ok"
        ],

        "remaining_budget": validation_result[
            "remaining_budget"
        ],

        "duplicate": validation_result[
            "duplicate"
        ],

        "duplicate_invoice_id": validation_result[
            "duplicate_invoice_id"
        ],

        "confidence_score": decision[
            "confidence_score"
        ],

        "confidence_threshold": decision[
            "confidence_threshold"
        ],

        "decision": decision[
            "decision"
        ],

        "reasons": decision[
            "reasons"
        ],
    }

    return response


@router.post(
    "/{invoice_id}"
)
def validate_invoice(
    invoice_id: int,

    budget_valid: bool,

    duplicate_flag: bool = False,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):

    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.invoice_id == invoice_id,
            Invoice.firm_id == current_user.firm_id,
        )
        .first()
    )

    if invoice is None:

        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    result = validate_and_route_invoice(
        db=db,
        invoice=invoice,
        budget_valid=budget_valid,
        duplicate_flag=duplicate_flag,
    )

    return {
        "invoice_id": invoice.invoice_id,
        "decision": result.decision,
        "reasons": result.reasons,
        "status": invoice.status,
    }