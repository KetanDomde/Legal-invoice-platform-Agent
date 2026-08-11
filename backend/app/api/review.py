from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import ADMIN, EDITOR, require_role
from app.database.database import get_db
from app.models import User
from app.schemas.review import (
    ApproveRequest,
    ClarificationRequest,
    RejectRequest,
    ReviewInvoiceResponse,
)
from app.services.invoice import (
    approve_invoice,
    get_invoice_for_review,
    get_review_queue,
    reject_invoice,
    request_clarification,
)


router = APIRouter(prefix="/review", tags=["Review Workflow"])


@router.get("/queue", response_model=list[ReviewInvoiceResponse])
def review_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    if current_user.firm_id is None:
        raise HTTPException(status_code=400, detail="Review queue requires a firm-scoped user.")
    return get_review_queue(db, current_user.firm_id)


@router.get("/{invoice_id}", response_model=ReviewInvoiceResponse)
def get_review_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    if current_user.firm_id is None:
        raise HTTPException(status_code=400, detail="Review requires a firm-scoped user.")
    try:
        invoice = get_invoice_for_review(db, invoice_id, current_user.firm_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return invoice


@router.post("/{invoice_id}/approve", response_model=ReviewInvoiceResponse)
def approve(
    invoice_id: int,
    request: ApproveRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    if current_user.firm_id is None:
        raise HTTPException(status_code=400, detail="Review requires a firm-scoped user.")
    try:
        invoice = get_invoice_for_review(db, invoice_id, current_user.firm_id)
        return approve_invoice(db, invoice, current_user.user_id, request.notes if request else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{invoice_id}/reject", response_model=ReviewInvoiceResponse)
def reject(
    invoice_id: int,
    request: RejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    if current_user.firm_id is None:
        raise HTTPException(status_code=400, detail="Review requires a firm-scoped user.")
    try:
        invoice = get_invoice_for_review(db, invoice_id, current_user.firm_id)
        return reject_invoice(db, invoice, current_user.user_id, request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{invoice_id}/clarify", response_model=ReviewInvoiceResponse)
def clarify(
    invoice_id: int,
    request: ClarificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    if current_user.firm_id is None:
        raise HTTPException(status_code=400, detail="Review requires a firm-scoped user.")
    try:
        invoice = get_invoice_for_review(db, invoice_id, current_user.firm_id)
        return request_clarification(db, invoice, current_user.user_id, request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
