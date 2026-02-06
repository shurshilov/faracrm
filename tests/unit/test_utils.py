"""
Unit tests for utility functions and helpers.

No database connection required.

Run: pytest tests/unit/test_utils.py -v -m unit
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

pytestmark = pytest.mark.unit


# ====================
# Password Validation
# ====================


class TestPasswordValidation:
    """Unit tests for password validation logic."""

    def test_min_length_pass(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password("longpass", {"min_length": 5})
        assert not any("too_short" in e for e in errors)

    def test_min_length_fail(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password("ab", {"min_length": 5})
        assert any("too_short" in e for e in errors)

    def test_min_length_exact(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password("abcde", {"min_length": 5})
        assert not any("too_short" in e for e in errors)

    def test_empty_password(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password("", {"min_length": 1})
        assert any("too_short" in e for e in errors)

    def test_require_uppercase_pass(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password(
            "Password", {"require_uppercase": True, "min_length": 1}
        )
        assert "no_uppercase" not in errors

    def test_require_uppercase_fail(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password(
            "password", {"require_uppercase": True, "min_length": 1}
        )
        assert "no_uppercase" in errors

    def test_require_uppercase_cyrillic(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password(
            "Пароль123", {"require_uppercase": True, "min_length": 1}
        )
        assert "no_uppercase" not in errors

    def test_require_lowercase_pass(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password(
            "pASSWORD", {"require_lowercase": True, "min_length": 1}
        )
        assert "no_lowercase" not in errors

    def test_require_lowercase_fail(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password(
            "PASSWORD", {"require_lowercase": True, "min_length": 1}
        )
        assert "no_lowercase" in errors

    def test_require_lowercase_cyrillic(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password(
            "пароль", {"require_lowercase": True, "min_length": 1}
        )
        assert "no_lowercase" not in errors

    def test_require_digits_pass(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password(
            "pass1word", {"require_digits": True, "min_length": 1}
        )
        assert "no_digit" not in errors

    def test_require_digits_fail(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password(
            "password", {"require_digits": True, "min_length": 1}
        )
        assert "no_digit" in errors

    def test_require_special_pass(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password(
            "pass!", {"require_special": True, "min_length": 1}
        )
        assert "no_special" not in errors

    def test_require_special_fail(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password(
            "password", {"require_special": True, "min_length": 1}
        )
        assert "no_special" in errors

    def test_require_special_various_chars(self):
        from backend.base.crm.users.models.users import User

        policy = {"require_special": True, "min_length": 1}
        for char in "!@#$%^&*()_+-=[]{}|;':\",./<>?`~":
            errors = User.validate_password(f"pass{char}", policy)
            assert (
                "no_special" not in errors
            ), f"Failed for special char: {char}"

    def test_all_requirements_pass(self):
        from backend.base.crm.users.models.users import User

        policy = {
            "min_length": 8,
            "require_uppercase": True,
            "require_lowercase": True,
            "require_digits": True,
            "require_special": True,
        }
        errors = User.validate_password("Password1!", policy)
        assert errors == []

    def test_all_requirements_all_fail(self):
        from backend.base.crm.users.models.users import User

        policy = {
            "min_length": 20,
            "require_uppercase": True,
            "require_lowercase": True,
            "require_digits": True,
            "require_special": True,
        }
        errors = User.validate_password("", policy)
        assert len(errors) >= 4

    def test_empty_policy(self):
        from backend.base.crm.users.models.users import User

        errors = User.validate_password("anything", {})
        assert errors == []

    def test_default_policy(self):
        from backend.base.crm.users.models.users import User

        policy = User._DEFAULT_PASSWORD_POLICY
        assert policy["min_length"] == 5
        assert policy["require_uppercase"] is False


# ====================
# Password Hash
# ====================


class TestPasswordHash:
    """Unit tests for password hashing."""

    def test_hash_deterministic(self):
        from backend.base.crm.users.models.users import User

        u = User.__new__(User)
        h1 = u.generate_password_hash("test", "salt")
        h2 = u.generate_password_hash("test", "salt")
        assert h1 == h2

    def test_hash_different_passwords(self):
        from backend.base.crm.users.models.users import User

        u = User.__new__(User)
        h1 = u.generate_password_hash("password1", "salt")
        h2 = u.generate_password_hash("password2", "salt")
        assert h1 != h2

    def test_hash_different_salts(self):
        from backend.base.crm.users.models.users import User

        u = User.__new__(User)
        h1 = u.generate_password_hash("same", "salt1")
        h2 = u.generate_password_hash("same", "salt2")
        assert h1 != h2

    def test_hash_is_hex_string(self):
        from backend.base.crm.users.models.users import User

        u = User.__new__(User)
        h = u.generate_password_hash("test", "salt")
        assert isinstance(h, str)
        assert len(h) > 0
        # hex string contains only hex chars
        int(h, 16)

    def test_hash_consistent_length(self):
        from backend.base.crm.users.models.users import User

        u = User.__new__(User)
        hashes = [
            u.generate_password_hash(f"pass{i}", f"salt{i}") for i in range(10)
        ]
        lengths = {len(h) for h in hashes}
        assert len(lengths) == 1  # All same length

    def test_hash_old_salt_method(self):
        from backend.base.crm.users.models.users import User

        u = User.__new__(User)
        u.password_salt = "my_salt"
        h1 = u.generate_password_hash_salt_old("password")
        h2 = u.generate_password_hash("password", "my_salt")
        assert h1 == h2

    def test_hash_unicode_password(self):
        from backend.base.crm.users.models.users import User

        u = User.__new__(User)
        h = u.generate_password_hash("пароль123!", "salt")
        assert isinstance(h, str)
        assert len(h) > 0

    def test_hash_empty_password(self):
        from backend.base.crm.users.models.users import User

        u = User.__new__(User)
        h = u.generate_password_hash("", "salt")
        assert isinstance(h, str)
        assert len(h) > 0


# ====================
# User Constants
# ====================


class TestUserConstants:
    """Tests for user constants."""

    def test_admin_user_id(self):
        from backend.base.crm.users.models.users import ADMIN_USER_ID

        assert ADMIN_USER_ID == 1

    def test_system_user_id(self):
        from backend.base.crm.users.models.users import SYSTEM_USER_ID

        assert SYSTEM_USER_ID == 2

    def test_constants_different(self):
        from backend.base.crm.users.models.users import (
            ADMIN_USER_ID,
            SYSTEM_USER_ID,
        )

        assert ADMIN_USER_ID != SYSTEM_USER_ID


# ====================
# Model Field Introspection
# ====================


class TestModelFields:
    """Unit tests for model field introspection."""

    def test_user_has_required_fields(self):
        from backend.base.crm.users.models.users import User

        fields = User.get_fields()
        required = {
            "id",
            "name",
            "login",
            "password_hash",
            "password_salt",
            "is_admin",
        }
        for f in required:
            assert f in fields, f"Missing field: {f}"

    def test_user_store_fields_exclude_m2m(self):
        from backend.base.crm.users.models.users import User

        store = User.get_store_fields()
        assert "role_ids" not in store
        assert "id" in store
        assert "name" in store

    def test_user_relation_fields(self):
        from backend.base.crm.users.models.users import User

        rels = User.get_relation_fields()
        names = [n for n, _ in rels]
        assert "image" in names
        assert "role_ids" in names

    def test_user_table_name(self):
        from backend.base.crm.users.models.users import User

        assert User.__table__ == "users"

    def test_partner_table_name(self):
        from backend.base.crm.partners.models.partners import Partner

        assert Partner.__table__ == "partners"

    def test_lead_table_name(self):
        from backend.base.crm.leads.models.leads import Lead

        assert Lead.__table__ == "leads"

    def test_sale_table_name(self):
        from backend.base.crm.sales.models.sale import Sale

        assert Sale.__table__ == "sales"

    def test_product_table_name(self):
        from backend.base.crm.products.models.product import Product

        assert Product.__table__ == "products"

    def test_role_table_name(self):
        from backend.base.crm.security.models.roles import Role

        assert Role.__table__ == "roles"

    def test_session_table_name(self):
        from backend.base.crm.security.models.sessions import Session

        assert Session.__table__ == "sessions"

    def test_product_has_selection_field(self):
        from backend.base.crm.products.models.product import Product

        fields = Product.get_fields()
        assert "type" in fields

    def test_lead_has_selection_field(self):
        from backend.base.crm.leads.models.leads import Lead

        fields = Lead.get_fields()
        assert "type" in fields


# ====================
# Schema Validation
# ====================


class TestSchemaValidation:
    """Unit tests for Pydantic schemas."""

    def test_signin_input_valid(self):
        from backend.base.crm.users.schemas.users import UserSigninInput

        data = UserSigninInput(login="admin", password="secret")
        assert data.login == "admin"
        assert data.password == "secret"

    def test_signin_input_extra_forbidden(self):
        from backend.base.crm.users.schemas.users import UserSigninInput

        with pytest.raises(Exception):
            UserSigninInput(login="admin", password="secret", extra="bad")

    def test_change_password_input(self):
        from backend.base.crm.users.schemas.users import ChangePasswordInput

        data = ChangePasswordInput(password="newpass123")
        assert data.password == "newpass123"
        assert data.user_id is None

    def test_change_password_with_user_id(self):
        from backend.base.crm.users.schemas.users import ChangePasswordInput

        data = ChangePasswordInput(user_id=42, password="newpass")
        assert data.user_id == 42

    def test_copy_user_input_defaults(self):
        from backend.base.crm.users.schemas.users import CopyUserInput

        data = CopyUserInput(
            source_user_id=1,
            name="Copy",
            login="copy_user",
        )
        assert data.copy_password is False
        assert data.copy_roles is True
        assert data.copy_files is False
        assert data.copy_languages is True
        assert data.copy_is_admin is True
        assert data.copy_contacts is False

    def test_copy_user_input_overrides(self):
        from backend.base.crm.users.schemas.users import CopyUserInput

        data = CopyUserInput(
            source_user_id=1,
            name="Copy",
            login="copy_user",
            copy_password=True,
            copy_roles=False,
            copy_contacts=True,
        )
        assert data.copy_password is True
        assert data.copy_roles is False
        assert data.copy_contacts is True

    def test_copy_user_output(self):
        from backend.base.crm.users.schemas.users import CopyUserOutput

        data = CopyUserOutput(id=1, name="Test", login="test")
        assert data.id == 1
        assert data.name == "Test"
        assert data.login == "test"
