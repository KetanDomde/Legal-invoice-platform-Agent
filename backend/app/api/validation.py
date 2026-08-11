from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.security import ADMIN, EDITOR, require_role
from app.database.database import get_db
from app.models import Invoice, User
from app.schemas.validation import ValidationRequest, ValidationResponse
from app.services.invoice import validate_and_route_invoice


router = APIRouter(prefix="/validation", tags=["Validation"])


@router.post("/{invoice_id}", response_model=ValidationResponse)
def validate(
    invoice_id: int,
    request: ValidationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ADMIN, EDITOR])),
):
    request = request or ValidationRequest(invoice_id=invoice_id)

    if request.invoice_id != invoice_id:
        raise HTTPException(status_code=400, detail="invoice_id does not match path")

    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.invoice_id == invoice_id,
            Invoice.firm_id == current_user.firm_id if current_user.firm_id is not None else True,
        )
        .first()
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    try:
        result = validate_and_route_invoice(
            db=db,
            invoice=invoice,
            confidence_score=request.confidence_score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"invoice_id": invoice_id, **result}
