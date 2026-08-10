from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.budget import Budget
from app.models.invoice import Invoice

def get_remaining_budget(
    db: Session,
    matter_id: int,
) -> float:
    """
    Calculate remaining budget for a matter.

    Remaining Budget =
        Allocated Budget - Sum of Approved Invoices
    """

    budget = (
        db.query(Budget)
        .filter(Budget.matter_id == matter_id)
        .first()
    )

    if budget is None:
        raise ValueError(
            f"No budget found for matter_id={matter_id}"
        )

    approved_spend = (
        db.query(
            func.coalesce(
                func.sum(Invoice.total_amount),
                0.0,
            )
        )
        .filter(
            Invoice.matter_id == matter_id,
            Invoice.status == "approved",
        )
        .scalar()
    )

    approved_spend = float(approved_spend or 0.0)

    remaining_budget = (
        float(budget.allocated_amt)
        - approved_spend
    )

    return remaining_budget


def validate_budget(
    db: Session,
    matter_id: int,
    invoice_amount: float,
) -> dict:
    """
    Validate invoice amount against remaining matter budget.
    """

    remaining_budget = get_remaining_budget(
        db=db,
        matter_id=matter_id,
    )

    invoice_amount = float(invoice_amount)

    budget_ok = (
        invoice_amount <= remaining_budget
    )

    if budget_ok:
        reason = "Invoice is within remaining budget."
    else:
        reason = (
            "Invoice amount exceeds "
            "remaining matter budget."
        )

    return {
        "budget_ok": budget_ok,
        "invoice_amount": invoice_amount,
        "remaining_budget": remaining_budget,
        "reason": reason,
    }