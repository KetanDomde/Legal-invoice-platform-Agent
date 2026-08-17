# from app.database.database import SessionLocal, engine
# from app.models.user import User
# from app.auth.password import hash_password
# from app.database.database import Base  # adjust if Base lives elsewhere

# Base.metadata.create_all(bind=engine)  # <-- creates tables if they don't exist yet

# db = SessionLocal()
# existing = (
#     db.query(User)
#     .filter(User.email == "admin@test.com")
#     .first()
# )

# if existing is None:
#     admin = User(
#         name="Admin",
#         email="admin@test.com",
#         password_hash=hash_password("admin123"),
#         role="admin",
#     )

#     db.add(admin)
#     db.commit()
#     print("Admin user created.")

# else:
#     print("Admin already exists.")

# db.close()


from app.database.database import SessionLocal, engine
from app.models.user import User
from app.auth.password import hash_password
from app.database.database import Base

Base.metadata.create_all(bind=engine)

db = SessionLocal()

users_to_seed = [
    {"name": "Admin", "email": "admin@test.com", "password": "admin123", "role": "admin"},
    {"name": "Editor", "email": "editor@test.com", "password": "editor123", "role": "editor"},
    {"name": "Viewer", "email": "viewer@test.com", "password": "viewer123", "role": "viewer"},
]

for user_data in users_to_seed:
    existing = db.query(User).filter(User.email == user_data["email"]).first()

    if existing is None:
        try:
            new_user = User(
                name=user_data["name"],
                email=user_data["email"],
                password_hash=hash_password(user_data["password"]),
                role=user_data["role"],
            )
            db.add(new_user)
            db.commit()
            print(f"{user_data['role'].capitalize()} user created ({user_data['email']}).")
        except Exception as e:
            db.rollback()
            print(f"FAILED to create {user_data['role']}: {e}")
    else:
        print(f"{user_data['role'].capitalize()} already exists ({user_data['email']}).")

db.close()