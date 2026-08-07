from decimal import Decimal
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from ..app.models import Firm, Budget, Invoice, Matter  # Adjust import based on your project structure
from ..app.service.bucket_tracker import get_remaining_budget  # Assuming function is in app.services


@pytest.fixture(name="session")
def session_fixture():
  engine = create_engine(
      "sqlite://",
      connect_args={"check_same_thread": False},
      poolclass=StaticPool,
  )
  SQLModel.metadata.create_all(engine)
  with Session(engine) as session:
    yield session


def test_get_remaining_budget(session: Session):
  # 1. Mock Data Setup
  firm = Firm(firm_id=1, name="Test Firm")
  matter = Matter(firm=firm, matter_id=1, name="Tech Patent Dispute", owner="Rajat", status="open")
  budget = Budget(budget_id=1, matter_id=1, allocated_amt=50000.0, threshold_pct=80.0)
  
  # Approved invoice (should count towards utilized budget)
  invoice_approved = Invoice(
      invoice_id=1,
      matter_id=1,
      invoice_no="INV-001",
      invoice_date="2026-06-01",
      total_amount=12000.0,
      status="approved",
  )
  
  # Pending invoice (should NOT count towards utilized budget)
  invoice_pending = Invoice(
      invoice_id=2,
      matter_id=1,
      invoice_no="INV-002",
      invoice_date="2026-06-05",
      total_amount=8000.0,
      status="submitted",
  )

  session.add(matter)
  session.add(budget)
  session.add(invoice_approved)
  session.add(invoice_pending)
  session.commit()

  # 2. Execute Function
  utilized, total, remaining = get_remaining_budget(session, matter_id=1)

  # 3. Assertions
  assert utilized == Decimal("12000.0")
  assert total == Decimal("50000.0")
  assert remaining == Decimal("38000.0")


def test_get_remaining_budget_no_budget_or_invoices(session: Session):
  # Matter with no budget and no invoices should gracefully handle defaults
  firm = Firm(name="Test Firm")
  matter = Matter(firm = firm, matter_id=2, name="Empty Matter", owner="Rajat", status="open")
  session.add(matter)
  session.commit()

  utilized, total, remaining = get_remaining_budget(session, matter_id=2)

  assert utilized == Decimal("0.00")
  assert total == Decimal("0.00")
  assert remaining == Decimal("0.00")