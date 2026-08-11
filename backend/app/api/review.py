from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.orm import Session

from app.database.database import get_db

from app.auth.dependencies import (
    require_role,
)

from app.auth.roles import (
    ADMIN,
    EDITOR,
)

from app.models.user import User

from app.schemas.review import (
    ReviewInvoiceResponse,
    ApproveRequest,
    RejectRequest,
    ClarificationRequest,
)

from app.workflow.review_queue import (
    get_review_queue,
)

from app.workflow.review_service import (
    get_invoice_for_review,
)

from app.workflow.approval_service import (
    approve_invoice,
)

from app.workflow.rejection_service import (
    reject_invoice,
)

from app.workflow.clarification_service import (
    request_clarification,
)


router = APIRouter(
    prefix="/review",
    tags=["Review Workflow"],
)


# ============================================================
# REVIEW QUEUE
# ============================================================

@router.get(
    "/queue",
    response_model=list[ReviewInvoiceResponse],
)
def review_queue(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """
    Return invoices waiting for human review.

    Only Admin and Editor can access
    the human-review queue.
    """

    invoices = get_review_queue(
        db=db,
        firm_id=current_user.firm_id,
    )

    return invoices


# ============================================================
# GET SINGLE INVOICE FOR REVIEW
# ============================================================

@router.get(
    "/{invoice_id}",
    response_model=ReviewInvoiceResponse,
)
def review_invoice(
    invoice_id: int,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """
    Get a specific invoice for review.

    Only Admin and Editor can review invoices.
    """

    try:

        invoice = get_invoice_for_review(
            db=db,
            invoice_id=invoice_id,
            firm_id=current_user.firm_id,
        )

        return invoice

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ============================================================
# APPROVE
# ============================================================

@router.post(
    "/{invoice_id}/approve",
    response_model=ReviewInvoiceResponse,
)
def approve(
    invoice_id: int,

    request: ApproveRequest,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """
    Approve an invoice.

    Only Admin and Editor can approve.
    """

    try:

        invoice = get_invoice_for_review(
            db=db,
            invoice_id=invoice_id,
            firm_id=current_user.firm_id,
        )

        return approve_invoice(
            db=db,
            invoice=invoice,
            user_id=current_user.user_id,
            notes=request.notes,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ============================================================
# REJECT
# ============================================================

@router.post(
    "/{invoice_id}/reject",
    response_model=ReviewInvoiceResponse,
)
def reject(
    invoice_id: int,

    request: RejectRequest,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """
    Reject an invoice.

    Rejection reason is mandatory.

    Only Admin and Editor can reject.
    """

    try:

        invoice = get_invoice_for_review(
            db=db,
            invoice_id=invoice_id,
            firm_id=current_user.firm_id,
        )

        return reject_invoice(
            db=db,
            invoice=invoice,
            user_id=current_user.user_id,
            reason=request.reason,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ============================================================
# CLARIFICATION
# ============================================================

@router.post(
    "/{invoice_id}/clarify",
    response_model=ReviewInvoiceResponse,
)
def clarify(
    invoice_id: int,

    request: ClarificationRequest,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """
    Request clarification for an invoice.

    Clarification note is mandatory.

    Only Admin and Editor can request clarification.
    """

    try:

        invoice = get_invoice_for_review(
            db=db,
            invoice_id=invoice_id,
            firm_id=current_user.firm_id,
        )

        return request_clarification(
            db=db,
            invoice=invoice,
            user_id=current_user.user_id,
            note=request.note,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )