from sqlalchemy.orm import Session

from app.auth.security import ADMIN, EDITOR, VIEWER, hash_password
from app.models import Firm, User
from app.services.invoice import add_audit_log


ALLOWED_ROLES = {ADMIN, EDITOR, VIEWER}


def validate_role(role: str) -> None:
    if role not in ALLOWED_ROLES:
        raise ValueError("Invalid role. Allowed roles are: admin, editor, viewer.")


def _ensure_firm_access(actor: User, target_firm_id: int | None) -> None:
    if actor.firm_id is not None and target_firm_id != actor.firm_id:
        raise ValueError("Cannot manage a user outside your own firm.")


def create_user(
    db: Session,
    *,
    actor: User,
    name: str,
    email: str,
    password: str,
    role: str,
    firm_id: int | None,
) -> User:
    validate_role(role)
    _ensure_firm_access(actor, firm_id)

    if db.query(User).filter(User.email == email).first():
        raise ValueError("A user with this email already exists.")
    if firm_id is not None and db.query(Firm).filter(Firm.firm_id == firm_id).first() is None:
        raise ValueError("Firm not found.")

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        firm_id=firm_id,
        is_active=True,
    )
    db.add(user)
    db.flush()

    add_audit_log(
        db,
        action="user_created",
        user_id=actor.user_id,
        notes=f"Created user {user.email} with role {user.role}.",
    )
    db.commit()
    db.refresh(user)
    return user


def deactivate_user(db: Session, *, actor: User, target_user_id: int) -> User:
    if target_user_id == actor.user_id:
        raise ValueError("An Admin cannot deactivate their own account.")

    user = db.query(User).filter(User.user_id == target_user_id).first()
    if user is None:
        raise ValueError("User not found.")
    _ensure_firm_access(actor, user.firm_id)

    if not user.is_active:
        raise ValueError("User is already deactivated.")

    user.is_active = False
    add_audit_log(
        db,
        action="user_deactivated",
        user_id=actor.user_id,
        notes=f"Deactivated user {user.email}.",
    )
    db.commit()
    db.refresh(user)
    return user


def change_user_role(db: Session, *, actor: User, target_user_id: int, new_role: str) -> User:
    validate_role(new_role)
    if target_user_id == actor.user_id:
        raise ValueError("An Admin cannot change their own role.")

    user = db.query(User).filter(User.user_id == target_user_id).first()
    if user is None:
        raise ValueError("User not found.")
    _ensure_firm_access(actor, user.firm_id)

    if user.role == new_role:
        raise ValueError("User already has this role.")

    old_role = user.role
    user.role = new_role
    add_audit_log(
        db,
        action="role_changed",
        user_id=actor.user_id,
        notes=f"Changed {user.email} role from {old_role} to {new_role}.",
    )
    db.commit()
    db.refresh(user)
    return user
