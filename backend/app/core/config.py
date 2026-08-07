"""
Central app configuration.
Switching databases (sqlite -> postgres) requires changing ONLY the
DATABASE_URL value (env var or .env file) — no code changes needed,
since SQLAlchemy picks the dialect/driver from the URL scheme.

sqlite:   sqlite+aiosqlite:///./app.db
postgres: postgresql+asyncpg://user:password@host:5432/dbname
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_PATH, extra="ignore")

    DATABASE_URL: str = "sqlite+aiosqlite:///./app.db"
    ECHO_SQL: bool = False
    JWT_SECRET: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    GROQ_API_KEY: str



settings = Settings()
