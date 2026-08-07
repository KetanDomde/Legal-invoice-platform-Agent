from app.database.database import SessionLocal
from app.models.user import User
from app.auth.password import hash_password

db = SessionLocal()
existing = (
    db.query(User)
    .filter(User.email == "admin@test.com")
    .first()
)

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

db.close()