from pathlib import Path

from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=str(ENV_PATH))

    DATABASE_URL: str
    JWT_SECRET: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    GROQ_API_KEY: str

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_sqlite_url(cls, value):
        if isinstance(value, str) and value.startswith("sqlite:///"):
            path_part = value[len("sqlite:///"):]
            if not path_part.startswith("/"):
                absolute_path = (BASE_DIR / path_part).resolve()
                return f"sqlite:///{absolute_path}"
        return value


settings = Settings()