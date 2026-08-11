from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import crud
from app.database.session import get_db
from app.models.user import User

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary")
def reports_summary(
    matter_id: Optional[int] = None,
    firm_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    effective_firm_id = current_user.firm_id if current_user.firm_id is not None else firm_id
    return crud.get_reports_summary(db, matter_id=matter_id, firm_id=effective_firm_id)
