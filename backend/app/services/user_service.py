from sqlalchemy.orm import Session

from app.models.user import User

from app.auth.roles import (
    ADMIN,
    EDITOR,
    VIEWER,
)

from app.auth.password import hash_password

from app.audit.audit_logger import (
    create_audit_log,
)


ALLOWED_ROLES = {
    ADMIN,
    EDITOR,
    VIEWER,
}


def validate_role(role: str):

    if role not in ALLOWED_ROLES:
        raise ValueError(
            "Invalid role. "
            "Allowed roles are: admin, editor, viewer."
        )


def create_user(
    db: Session,
    name: str,
    email: str,
    password: str,
    role: str,
    firm_id: int | None,
    actor_user_id: int,
    actor_firm_id: int | None,   # ADD THIS LINE

):
    """
    Admin creates a new user.
    """

    validate_role(role)

      # ADD THIS BLOCK
    if actor_firm_id is not None and firm_id != actor_firm_id:
        raise ValueError(
            "Cannot create a user outside your own firm."
        )
        
    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user is not None:
        raise ValueError(
            "A user with this email already exists."
        )

    if len(password) < 8:
        raise ValueError(
            "Password must contain at least 8 characters."
        )

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        firm_id=firm_id,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    create_audit_log(
        db=db,
        action="user_created",
        user_id=actor_user_id,
        invoice_id=None,
        notes=(
            f"Created user {user.email} "
            f"with role {user.role}."
        ),
    )

    return user


def deactivate_user(
    db: Session,
    target_user_id: int,
    actor_user_id: int,
    actor_firm_id: int | None,   # ADD THIS LINE

):
    """
    Admin deactivates another user.
    """

    if target_user_id == actor_user_id:
        raise ValueError(
            "An Admin cannot deactivate their own account."
        )

    user = (
        db.query(User)
        .filter(
            User.user_id == target_user_id
        )
        .first()
    )

    if user is None:
        raise ValueError(
            "User not found."
        )

     # ADD THIS BLOCK
    if actor_firm_id is not None and user.firm_id != actor_firm_id:
        raise ValueError(
            "Cannot manage a user outside your own firm."
        )


    if not user.is_active:
        raise ValueError(
            "User is already deactivated."
        )

    user.is_active = False

    db.add(user)
    db.commit()
    db.refresh(user)

    create_audit_log(
        db=db,
        action="user_deactivated",
        user_id=actor_user_id,
        invoice_id=None,
        notes=(
            f"Deactivated user {user.email}."
        ),
    )

    return user


def change_user_role(
    db: Session,
    target_user_id: int,
    new_role: str,
    actor_user_id: int,
    actor_firm_id: int | None,   # ADD THIS LINE

):
    """
    Admin changes another user's role.
    """

    validate_role(new_role)

    if target_user_id == actor_user_id:
        raise ValueError(
            "An Admin cannot change their own role."
        )

    user = (
        db.query(User)
        .filter(
            User.user_id == target_user_id
        )
        .first()
    )

    if user is None:
        raise ValueError(
            "User not found."
        )

      # ADD THIS BLOCK
    if actor_firm_id is not None and user.firm_id != actor_firm_id:
        raise ValueError(
            "Cannot manage a user outside your own firm."
        )
        
        
    old_role = user.role

    if old_role == new_role:
        raise ValueError(
            "User already has this role."
        )

    user.role = new_role

    db.add(user)
    db.commit()
    db.refresh(user)

    create_audit_log(
        db=db,
        action="role_changed",
        user_id=actor_user_id,
        invoice_id=None,
        notes=(
            f"Changed {user.email} "
            f"role from {old_role} "
            f"to {new_role}."
        ),
    )

    return user