from app.models.user import User
from app.auth.password import hash_password
from app.auth.jwt_handler import create_access_token

def create_test_user(
    db,
    email,
    role,
    firm_id=1,
):
    user = User(
        name=f"{role} Test",
        email=email,
        password_hash=hash_password(
            "Password123!"
        ),
        role=role,
        firm_id=firm_id,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user

def get_token(user):
    return create_access_token(
        {
            "user_id": user.user_id,
            "role": user.role,
        }
    )

def test_admin_can_access_review_queue(
    client,
    db,
):
    user = create_test_user(
        db,
        "admin@test.com",
        "admin",
    )

    token = get_token(user)
    response = client.get(
        "/review/queue",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
    )
    assert response.status_code == 200

def test_editor_can_access_review_queue(
    client,
    db,
):
    user = create_test_user(
        db,
        "editor@test.com",
        "editor",
    )

    token = get_token(user)

    response = client.get(
        "/review/queue",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
    )

    assert response.status_code == 200


def test_viewer_cannot_access_review_queue(
    client,
    db,
):
    user = create_test_user(
        db,
        "viewer@test.com",
        "viewer",
    )

    token = get_token(user)

    response = client.get(
        "/review/queue",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
    )

    assert response.status_code == 403
    

def test_without_token_cannot_access_review_queue(
    client,
):
    response = client.get(
        "/review/queue"
    )

    assert response.status_code in [
        401,
        403,
    ]
    

def test_deactivated_user_cannot_access_api(
    client,
    db,
):
    user = create_test_user(
        db,
        "inactive@test.com",
        "admin",
    )

    user.is_active = False
    db.commit()
    token = get_token(user)
    response = client.get(
        "/review/queue",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
    )

    assert response.status_code == 403