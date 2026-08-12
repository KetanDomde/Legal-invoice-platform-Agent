from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings


def _normalize_sqlite_url(database_url: str) -> str:
    if not database_url.startswith("sqlite:///"):
        return database_url

    path_part = database_url[len("sqlite:///"):]
    if path_part.startswith("/"):
        return database_url

    base_dir = Path(__file__).resolve().parents[2]
    absolute_path = (base_dir / path_part).resolve()
    return f"sqlite:///{absolute_path}"


RESOLVED_DATABASE_URL = _normalize_sqlite_url(settings.DATABASE_URL)
engine = create_engine(
    RESOLVED_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()