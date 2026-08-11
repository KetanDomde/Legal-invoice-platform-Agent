"""
Day 1 seed script (Rajat: 1 firm/1 matter/1 budget; Trinkesh: 1 default Admin
user) — rebuilt for SQLAlchemy. Run with: python -m app.seed
Safe to re-run — skips rows that already exist by natural key.
"""
from app.auth.password import hash_password
from app.core.config import settings
from app.database.session import SessionLocal, init_db
from app.models.firm import Firm
from app.models.matter import Matter
from app.models.budget import Budget
from app.models.user import User


def seed():
    init_db()
    db = SessionLocal()
    try:
        firm = db.query(Firm).filter(Firm.name == "Sample Outside Counsel LLP").first()
        if firm:
            print(f"Firm already exists (firm_id={firm.firm_id}), skipping.")
        else:
            firm = Firm(name="Sample Outside Counsel LLP", contact_email="billing@samplecounsel.example")
            db.add(firm)
            db.commit()
            db.refresh(firm)
            print(f"Created firm_id={firm.firm_id}")

        matter = db.query(Matter).filter(Matter.firm_id == firm.firm_id).first()
        if matter:
            print(f"Matter already exists (matter_id={matter.matter_id}), skipping.")
        else:
            matter = Matter(firm_id=firm.firm_id, name="Acme Corp v. Doe — Contract Dispute", owner="Ketan Domde")
            db.add(matter)
            db.commit()
            db.refresh(matter)
            print(f"Created matter_id={matter.matter_id}")

        budget = db.query(Budget).filter(Budget.matter_id == matter.matter_id).first()
        if budget:
            print(f"Budget already exists (budget_id={budget.budget_id}), skipping.")
        else:
            budget = Budget(matter_id=matter.matter_id, allocated_amt=50000.0, threshold_pct=80)
            db.add(budget)
            db.commit()
            db.refresh(budget)
            print(f"Created budget_id={budget.budget_id} (allocated $50,000, 80% threshold)")

        existing_admin = db.query(User).filter(User.email == settings.DEFAULT_ADMIN_EMAIL).first()
        if existing_admin:
            print(f"Admin user already exists ({settings.DEFAULT_ADMIN_EMAIL}), skipping.")
        else:
            admin = User(
                name="Default Admin", email=settings.DEFAULT_ADMIN_EMAIL,
                password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD), role="admin", firm_id=None,
            )
            db.add(admin)
            db.commit()
            print(f"Created default Admin user: {settings.DEFAULT_ADMIN_EMAIL} / (password from .env)")

        print("\nSeed complete. matter_id to use for the Day 2 demo:", matter.matter_id)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
