# TODO: api review.py
 
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
 
from app.auth.security import ADMIN, EDITOR, require_role
from app.database.database import get_db
from app.models import User
from app.schemas.review import ReviewInvoiceResponse
from app.services.invoice import (
    approve_invoice,
    get_invoice_for_review,
    get_review_queue,
    get_review_reasons,
    reject_invoice,
    request_clarification,
)
 
router = APIRouter(prefix="/review", tags=["Review Workflow"])
 
 
def _to_response(invoice) -> ReviewInvoiceResponse:
    """Build the API response, filling in review_reasons which isn't a
    column on the Invoice model (only present on the /queue dict shape)."""
    data = ReviewInvoiceResponse.model_validate(invoice)
    data.review_reasons = get_review_reasons(invoice)
    return data
 
 
@router.get("/queue", response_model=list[ReviewInvoiceResponse])
def review_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    # firm_id=None is a global user (see app/api/users.py, billing.py, etc.
    # for the same convention) — they see the queue across all firms.
    return get_review_queue(db, current_user.firm_id)
 
 
def _get_invoice(db: Session, invoice_id: int, current_user: User):
    try:
        return get_invoice_for_review(db, invoice_id, current_user.firm_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
 
 
@router.get("/{invoice_id}", response_model=ReviewInvoiceResponse)
def get_review_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    invoice = _get_invoice(db, invoice_id, current_user)
    return _to_response(invoice)
 
 
@router.post("/{invoice_id}/approve", response_model=ReviewInvoiceResponse)
def approve(
    invoice_id: int,
    notes: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    invoice = _get_invoice(db, invoice_id, current_user)
    try:
        invoice = approve_invoice(db, invoice, current_user.user_id, notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_response(invoice)
 
 
@router.post("/{invoice_id}/reject", response_model=ReviewInvoiceResponse)
def reject(
    invoice_id: int,
    reason: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    invoice = _get_invoice(db, invoice_id, current_user)
    try:
        invoice = reject_invoice(db, invoice, current_user.user_id, reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_response(invoice)
 
 
@router.post("/{invoice_id}/clarify", response_model=ReviewInvoiceResponse)
def clarify(
    invoice_id: int,
    reason: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    invoice = _get_invoice(db, invoice_id, current_user)
    try:
        invoice = request_clarification(db, invoice, current_user.user_id, reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_response(invoice)
 