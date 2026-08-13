import pytest
from fastapi import HTTPException
from app.auth.dependencies import (
    require_role,
)
from app.auth.roles import (
    ADMIN,
    EDITOR,
    VIEWER,
)

def test_admin_can_access_review():
    checker = require_role(
        [ADMIN, EDITOR]
    )

    class Admin:
        role = ADMIN

    user = checker(Admin())
    assert user.role == ADMIN

def test_editor_can_access_review():

    checker = require_role(
        [ADMIN, EDITOR]
    )

    class Editor:
        role = EDITOR

    user = checker(Editor())
    assert user.role == EDITOR

def test_viewer_cannot_access_review():
    checker = require_role(
        [ADMIN, EDITOR]
    )

    class Viewer:
        role = VIEWER

    with pytest.raises(
        HTTPException
    ) as exc:

        checker(Viewer())

    assert exc.value.status_code == 403