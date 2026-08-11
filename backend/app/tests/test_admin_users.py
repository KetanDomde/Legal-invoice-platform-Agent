from unittest.mock import Mock
import pytest
from app.auth.roles import (
    ADMIN,
    EDITOR,
    VIEWER,
)
from app.services.user_service import (
    validate_role,
)

def test_valid_roles():
    validate_role(ADMIN)
    validate_role(EDITOR)
    validate_role(VIEWER)

def test_invalid_role():
    with pytest.raises(
        ValueError
    ):
        validate_role("superadmin")

def test_invalid_role_is_rejected():
    with pytest.raises(
        ValueError
    ):
        validate_role("user")   