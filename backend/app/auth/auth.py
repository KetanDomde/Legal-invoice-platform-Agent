from sqlalchemy.orm import Session

from app.models.user import User
from app.auth.password import verify_password
from app.auth.jwt_handler import create_access_token


def authenticate_user(
    db: Session,
    email: str,
    password: str,
):

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        return None

    if not verify_password(
        password,
        user.password_hash,
    ):
        return None

    token = create_access_token(
        {
            "user_id": user.user_id,
            "role": user.role,
            "firm_id": user.firm_id,
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }