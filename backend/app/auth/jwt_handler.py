from datetime import datetime, timedelta
from jose import jwt

from app.core.config import settings


def create_access_token(data: dict):

    payload = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload.update(
        {"exp": expire}
    )

    token = jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.ALGORITHM,
    )

    return token


def decode_access_token(token: str):

    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.ALGORITHM],
    )