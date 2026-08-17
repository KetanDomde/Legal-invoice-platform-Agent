

from app.database.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.firm import Firm
from app.models.matter import Matter
from app.models.budget import Budget
from app.auth.password import hash_password


def init_db():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # --- Admin user ---
        existing = db.query(User).filter(User.email == "admin@test.com").first()
        if existing is None:
            admin = User(
                name="Admin",
                email="admin@test.com",
                password_hash=hash_password("admin123"),
                role="admin",
            )
            db.add(admin)
            db.commit()
            print("Admin user created.")
        else:
            print("Admin already exists.")

        # --- Firm / Matter / Budget seed ---
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

    finally:
        db.close()


def delete_db():
    """Drops all tables on app shutdown."""
    Base.metadata.drop_all(bind=engine)
    print("Database tables dropped on shutdown.")