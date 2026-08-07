from decimal import Decimal
from sqlmodel import Session, func, select
from ..models import Budget, Invoice


def get_remaining_budget(
    session: Session, matter_id: int
) -> tuple[Decimal, Decimal, Decimal]:
  """For a given matter, first find the allocated budget for the matter

  then, find the sum of invoices that are in approved status regarding the matter
  Finally, subtract the 2 quantities and return as result.
  Return should have 3 values - utilized_budget, total_budget, remaining_budget
  """
  # 1. Fetch allocated budget for the matter
  budget = session.exec(
      select(Budget).where(Budget.matter_id == matter_id)
  ).first()

  total_budget = Decimal(str(budget.allocated_amt)) if budget else Decimal("0.00")

  # 2. Find the sum of approved invoices for this matter
  utilized_stmt = select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(
      Invoice.matter_id == matter_id, Invoice.status == "approved"
  )
  utilized_result = session.exec(utilized_stmt).first()

  utilized_budget = (
      Decimal(str(utilized_result))
      if utilized_result is not None
      else Decimal("0.00")
  )

  # 3. Calculate remaining budget
  remaining_budget = total_budget - utilized_budget

  return utilized_budget, total_budget, remaining_budget