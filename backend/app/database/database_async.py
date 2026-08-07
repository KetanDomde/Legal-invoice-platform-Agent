"""
Async DB engine/session setup. Works unchanged for sqlite or postgres —
only app.config.settings.DATABASE_URL changes between environments.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# sqlite (file-based, single-process dev db) needs this flag; postgres does not.
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_async_engine(settings.DATABASE_URL, echo=settings.ECHO_SQL, connect_args=connect_args)

AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """Create tables on startup. For production use Alembic migrations instead."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
