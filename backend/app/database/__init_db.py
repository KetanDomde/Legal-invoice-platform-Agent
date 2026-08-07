from app.database.database import Base, engine
from sqlmodel import SQLModel

# Import all models
from app.models import (
    Firm,
    User,
    Matter,
    Budget,
    Invoice,
    AuditLog,
    BudgetLedger,
    Alert,
    LineItem,
    role
)

async def create_db_and_tables():
    async with async_engine.begin() as conn:
      # run_sync executes the synchronous metadata create_all inside the async connection context
      await conn.run_sync(SQLModel.metadata.create_all)


print("Database tables created successfully.")