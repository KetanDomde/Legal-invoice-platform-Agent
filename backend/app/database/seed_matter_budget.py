"""
Seed script: creates a Firm, Matter, and Budget so validate_invoice()
can be tested/run for matter_id=1, firm_id=1.

Run from backend/:
    python -m app.database.seed_matter_budget
(or copy this into app/database/ first)
"""

from app.database.database import SessionLocal
from app.models.firm import Firm
from app.models.matter import Matter
from app.models.budget import Budget

db = SessionLocal()

try:
    firm = db.query(Firm).filter(Firm.firm_id == 1).first()
    if firm is None:
        firm = Firm(
            firm_id=1,
            name="Sample Outside Counsel LLP",
            contact_email="contact@samplefirm.com",
            status="active",
        )
        db.add(firm)
        db.commit()
        print(f"Created firm: {firm.name} (firm_id={firm.firm_id})")
    else:
        print(f"Firm already exists: {firm.name} (firm_id={firm.firm_id})")

    matter = db.query(Matter).filter(Matter.matter_id == 1).first()
    if matter is None:
        matter = Matter(
            matter_id=1,
            firm_id=1,
            name="Sample Litigation Matter",
            owner="Trinkesh",
            status="open",
        )
        db.add(matter)
        db.commit()
        print(f"Created matter: {matter.name} (matter_id={matter.matter_id})")
    else:
        print(f"Matter already exists: {matter.name} (matter_id={matter.matter_id})")

    budget = db.query(Budget).filter(Budget.matter_id == 1).first()
    if budget is None:
        budget = Budget(
            matter_id=1,
            allocated_amt=50000.0,
            threshold_pct=80,
        )
        db.add(budget)
        db.commit()
        print(f"Created budget: allocated_amt={budget.allocated_amt} for matter_id={budget.matter_id}")
    else:
        print(f"Budget already exists: allocated_amt={budget.allocated_amt} for matter_id={budget.matter_id}")

    print("\nSeed complete. matter_id=1 / firm_id=1 is ready for validate_invoice().")

finally:
    db.close()