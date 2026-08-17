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
        # --- Users (admin / editor / viewer) ---
        users_to_seed = [
            {"name": "Admin", "email": "admin@test.com", "password": "admin123", "role": "admin"},
            {"name": "Editor", "email": "editor@test.com", "password": "editor123", "role": "editor"},
            {"name": "Viewer", "email": "viewer@test.com", "password": "viewer123", "role": "viewer"},
        ]

        for user_data in users_to_seed:
            existing = db.query(User).filter(User.email == user_data["email"]).first()
            if existing is None:
                user = User(
                    name=user_data["name"],
                    email=user_data["email"],
                    password_hash=hash_password(user_data["password"]),
                    role=user_data["role"],
                )
                db.add(user)
                db.commit()
                print(f"{user_data['role'].capitalize()} user created ({user_data['email']}).")
            else:
                print(f"{user_data['role'].capitalize()} already exists ({user_data['email']}).")

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