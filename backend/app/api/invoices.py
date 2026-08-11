import shutil
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.database import crud
from app.database.session import get_db
from app.models.user import User
from app.workflows.legal_invoice_platform_agent import run_pipeline

router = APIRouter(prefix="/invoices", tags=["invoices"])


class SubmitInvoiceResponse(BaseModel):
    invoice_id: Optional[int]
    final_status: str
    confidence_score: float
    extracted: dict
    validation_reason: str


@router.post("/submit", response_model=SubmitInvoiceResponse)
def submit_invoice(
    matter_id: int = Form(...),
    firm_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(["admin", "editor"])),
):
    """Runs one invoice fully through the LangGraph pipeline. Requires Admin or Editor."""
    with tempfile.NamedTemporaryFile(delete=False, suffix="_" + file.filename) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    result = run_pipeline(tmp_path, matter_id, firm_id)
    return SubmitInvoiceResponse(
        invoice_id=result.get("invoice_id"),
        final_status=result.get("final_status", "unknown"),
        confidence_score=result.get("confidence_score", 0.0),
        extracted=result.get("extracted", {}),
        validation_reason=result.get("validation_reason", ""),
    )


@router.get("/{invoice_id}/status")
def get_invoice_status(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    invoice = crud.get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if current_user.firm_id is not None and invoice.firm_id != current_user.firm_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted to view this firm's invoices")
    return {
        "invoice_id": invoice.invoice_id, "matter_id": invoice.matter_id, "firm_id": invoice.firm_id,
        "invoice_no": invoice.invoice_no, "invoice_date": invoice.invoice_date,
        "total_amount": invoice.total_amount, "status": invoice.status, "confidence_score": invoice.confidence_score,
    }


@router.get("/review-queue")
def get_review_queue(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    invoices = crud.list_review_queue(db, firm_id=current_user.firm_id)
    return [
        {"invoice_id": i.invoice_id, "matter_id": i.matter_id, "firm_id": i.firm_id, "invoice_no": i.invoice_no,
         "invoice_date": i.invoice_date, "total_amount": i.total_amount, "status": i.status,
         "confidence_score": i.confidence_score}
        for i in invoices
    ]


class ReviewActionRequest(BaseModel):
    notes: str = ""


@router.post("/{invoice_id}/approve")
def approve_invoice(
    invoice_id: int,
    payload: ReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "editor"])),
):
    invoice = crud.get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.status != "pending_review":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invoice is '{invoice.status}', not pending review")

    budget_info = crud.get_remaining_budget(db, invoice.matter_id)
    alert_msg = None
    if budget_info["has_budget"]:
        crud.record_ledger_entry(db, budget_info["budget_id"], invoice_id, invoice.total_amount)
        alert_msg = crud.create_alert_if_threshold_crossed(db, budget_info["budget_id"])
    crud.update_invoice_status(db, invoice_id, "approved")
    crud.write_audit_log(db, "approved", invoice_id=invoice_id, user_id=current_user.user_id, notes=payload.notes)
    return {"invoice_id": invoice_id, "status": "approved", "alert": alert_msg}


@router.post("/{invoice_id}/reject")
def reject_invoice(
    invoice_id: int,
    payload: ReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "editor"])),
):
    if not payload.notes.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="notes are required to reject an invoice (PRD FR-13)")
    invoice = crud.get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.status != "pending_review":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invoice is '{invoice.status}', not pending review")

    crud.update_invoice_status(db, invoice_id, "rejected")
    crud.write_audit_log(db, "rejected", invoice_id=invoice_id, user_id=current_user.user_id, notes=payload.notes)
    return {"invoice_id": invoice_id, "status": "rejected"}
