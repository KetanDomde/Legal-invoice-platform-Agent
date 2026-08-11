"""
Settings — filled in because app/auth/jwt_handler.py already imports
`from app.core.config import settings` and expects settings.JWT_SECRET,
settings.ALGORITHM, settings.ACCESS_TOKEN_EXPIRE_MINUTES. Names below match
exactly what his code already calls, so nothing in app/auth/ needs to change.
"""
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change_this_to_a_long_random_string")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))  # 8 hours

    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")

    DEFAULT_ADMIN_EMAIL: str = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@konverge.ai")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "ChangeMe123!")


settings = Settings()
