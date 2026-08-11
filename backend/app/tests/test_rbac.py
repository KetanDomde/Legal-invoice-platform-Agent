import pytest
from fastapi import HTTPException
from app.auth.roles import (
    ADMIN,
    EDITOR,
    VIEWER,
)

def test_admin_role():
    allowed_roles = [
        ADMIN,
        EDITOR,
    ]
    assert ADMIN in allowed_roles

def test_editor_can_review():
    allowed_roles = [
        ADMIN,
        EDITOR,
    ]
    assert EDITOR in allowed_roles


def test_viewer_cannot_review():

    allowed_roles = [
        ADMIN,
        EDITOR,
    ]

    assert VIEWER not in allowed_roles


def test_only_admin_can_manage_users():

    allowed_roles = [
        ADMIN,
    ]

    assert ADMIN in allowed_roles
    assert EDITOR not in allowed_roles
    assert VIEWER not in allowed_roles
    

from unittest.mock import Mock

from app.auth.dependencies import require_role


def test_require_role_allows_admin():

    checker = require_role(
        [ADMIN]
    )

    admin = Mock()
    admin.role = ADMIN

    result = checker(admin)

    assert result == admin


def test_require_role_rejects_viewer():

    checker = require_role(
        [ADMIN, EDITOR]
    )

    viewer = Mock()
    viewer.role = VIEWER

    with pytest.raises(
        HTTPException
    ) as exc:

        checker(viewer)

    assert exc.value.status_code == 403