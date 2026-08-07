from app.database.database import Base, engine

# Import all models
from app.models import (
    Firm,
    User,
    Matter,
    Budget,
    Invoice,
    AuditLog,
)

Base.metadata.create_all(bind=engine)

print("Database tables created successfully.")