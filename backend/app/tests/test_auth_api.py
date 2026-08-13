from app.models.user import User
from app.auth.password import hash_password


def create_user(
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
def test_login_returns_token(client, db):
    create_user(db, "admin@test.com", "admin")

    response = client.post(
        "/auth/login",
        json={
            "email": "admin@test.com",
            "password": "Password123!",
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"