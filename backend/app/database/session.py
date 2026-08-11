"""
SQLAlchemy engine/session setup. Rajat's territory long-term — this exists
so the app.models.* classes (which app/auth/auth.py already depends on)
have a Base to inherit from and a session to run against.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

os.makedirs("data", exist_ok=True)

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a session, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Creates all tables from the models registered against Base. Migration-light
    per ERD.docx — delete data/app.db and re-run app.seed to reset during the sprint."""
    import app.models  # noqa: F401 — ensures every model module registers with Base before create_all
    Base.metadata.create_all(bind=engine)
