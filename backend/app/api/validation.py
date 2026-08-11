from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.security import ADMIN, EDITOR, require_role
from app.database.database import get_db
from app.models import Invoice, User
from app.services.invoice import validate_and_route_invoice

router = APIRouter(prefix="/validation", tags=["Validation"])


@router.post("/{invoice_id}")
def validate(
    invoice_id: int,
    budget_valid: bool | None = Query(default=None),
    duplicate_flag: bool = Query(default=False),
    confidence_score: float | None = Query(default=None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    query = db.query(Invoice).filter(Invoice.invoice_id == invoice_id)
    if current_user.firm_id is not None:
        query = query.filter(Invoice.firm_id == current_user.firm_id)
    invoice = query.first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    result = validate_and_route_invoice(
        db=db,
        invoice=invoice,
        confidence_score=confidence_score,
        budget_valid=budget_valid,
        duplicate_flag=duplicate_flag if budget_valid is not None else None,
    )
    return {
        "invoice_id": invoice.invoice_id,
        "decision": result["decision"],
        "reasons": result["reasons"],
        "status": invoice.status,
        **{k: v for k, v in result.items() if k not in {"decision", "reasons"}},
    }
