from app.models.user import User
from app.auth.password import hash_password
from app.auth.jwt_handler import create_access_token

def create_user(
    db,
    email,
    role,
):
    user = User(
        name=f"{role} Test",
        email=email,
        password_hash=hash_password(
            "Password123!"
        ),
        role=role,
        firm_id=1,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user

def token_for(user):
    return create_access_token(
        {
            "user_id": user.user_id,
            "role": user.role,
        }
    )

def test_only_admin_can_create_user(
    client,
    db,
):
    editor = create_user(
        db,
        "editor@test.com",
        "editor",
    )

    token = token_for(editor)

    response = client.post(
        "/admin/users",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
        json={
            "name": "New Viewer",
            "email": "newviewer@test.com",
            "password": "Password123!",
            "role": "viewer",
            "firm_id": 1,
        },
    )

    assert response.status_code == 403
    
## test admin role chnages.

def test_admin_can_create_user(
    client,
    db,
):
    admin = create_user(
        db,
        "admin@test.com",
        "admin",
    )

    token = token_for(admin)

    response = client.post(
        "/admin/users",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
        json={
            "name": "New Viewer",
            "email": "newviewer@test.com",
            "password": "Password123!",
            "role": "viewer",
            "firm_id": 1,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["email"] == "newviewer@test.com"
    assert data["role"] == "viewer"
    assert data["is_active"] is True
    
    
## test admin deactivate..

def test_admin_can_deactivate_user(
    client,
    db,
):
    admin = create_user(
        db,
        "admin3@test.com",
        "admin",
    )

    viewer = create_user(
        db,
        "viewer3@test.com",
        "viewer",
    )

    token = token_for(admin)

    response = client.patch(
        f"/admin/users/{viewer.user_id}/deactivate",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["is_active"] is False
    

## test viwer cannot chnage the managed user 

def test_viewer_cannot_change_role(
    client,
    db,
):
    viewer = create_user(
        db,
        "viewer4@test.com",
        "viewer",
    )

    target = create_user(
        db,
        "target@test.com",
        "editor",
    )

    token = token_for(viewer)

    response = client.patch(
        f"/admin/users/{target.user_id}/role",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
        json={
            "role": "admin"
        },
    )

    assert response.status_code == 403
    
