# app/core/config.py
import os
from pydantic_settings import BaseSettings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/

class Settings(BaseSettings):
    DATABASE_URL: str = f"sqlite:///{os.path.join(BASE_DIR, 'legal_invoice.db')}"
    JWT_SECRET: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    GROQ_API_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()