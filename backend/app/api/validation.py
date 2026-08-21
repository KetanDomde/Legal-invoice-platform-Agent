from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.security import ADMIN, EDITOR, require_role
from app.database.database import get_db
from app.models import Invoice, User
from app.services.invoice import validate_and_route_invoice


router = APIRouter(
    prefix="/validation",
    tags=["Validation"],
)


@router.post("/{invoice_id}")
def validate(
    invoice_id: int,
    duplicate_flag: bool | None = Query(default=None),
    confidence_score: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role([ADMIN, EDITOR])
    ),
):
    """
    Re-run server-side validation.

    Budget validity is intentionally NOT accepted from the client.
    It is always calculated from the canonical BudgetLedger summary.
    """

    query = db.query(Invoice).filter(
        Invoice.invoice_id == invoice_id
    )

    if current_user.firm_id is not None:
        query = query.filter(
            Invoice.firm_id == current_user.firm_id
        )

    invoice = query.first()

    if invoice is None:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    result = validate_and_route_invoice(
        db=db,
        invoice=invoice,
        confidence_score=confidence_score,
        duplicate_flag=duplicate_flag,
    )

    return {
        "invoice_id": invoice.invoice_id,
        "decision": result["decision"],
        "reasons": result["reasons"],
        "status": invoice.status,
        **{
            key: value
            for key, value in result.items()
            if key not in {"decision", "reasons"}
        },
    }