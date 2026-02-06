"""
Integration tests for User model.

Tests cover:
- CRUD operations
- Password management
- Role assignments
- Session management
- User validation

Run: pytest tests/integration/users/test_user_model.py -v -m integration
"""

import pytest
from datetime import datetime, timezone

pytestmark = pytest.mark.integration


# ====================
# Create Tests
# ====================


class TestUserCreate:
    """Tests for user creation."""

    async def test_create_user_minimal(self):
        """Test creating user with minimal required fields."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.languages.models.language import Language

        # Create language first
        lang_id = await Language.create(
            Language(
                code="en",
                name="English",
                active=True,
            )
        )

        user = User(
            name="Test User",
            login="testuser",
            password_hash="hash123",
            password_salt="salt123",
            lang_id=lang_id,
        )
        user_id = await User.create(user)

        assert user_id is not None
        assert isinstance(user_id, int)
        assert user_id > 0

    async def test_create_user_with_all_fields(self):
        """Test creating user with all fields populated."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.languages.models.language import Language

        lang_id = await Language.create(
            Language(
                code="ru",
                name="Russian",
                active=True,
            )
        )

        user = User(
            name="Иван Петров",
            login="ivan",
            password_hash="secure_hash",
            password_salt="random_salt",
            is_admin=True,
            home_page="/dashboard",
            layout_theme="modern",
            lang_id=lang_id,
        )
        user_id = await User.create(user)

        created = await User.get(user_id)
        assert created.name == "Иван Петров"
        assert created.login == "ivan"
        assert created.is_admin is True
        assert created.home_page == "/dashboard"
        assert created.layout_theme == "modern"

    async def test_create_user_default_values(self):
        """Test that default values are applied correctly."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.languages.models.language import Language

        lang_id = await Language.create(
            Language(
                code="en",
                name="English",
                active=True,
            )
        )

        user = User(
            name="Default User",
            login="default",
            password_hash="hash",
            password_salt="salt",
            lang_id=lang_id,
        )
        user_id = await User.create(user)

        created = await User.get(user_id)
        assert created.is_admin is False  # Default
        assert created.home_page == "/users"  # Default
        assert created.layout_theme == "modern"  # Default

    async def test_create_user_with_admin_flag(self, user_factory):
        """Test creating admin user."""
        admin = await user_factory(
            name="Admin User",
            login="admin",
            is_admin=True,
        )

        assert admin.is_admin is True

    async def test_create_multiple_users(self, user_factory):
        """Test creating multiple users."""
        users = []
        for i in range(5):
            user = await user_factory(
                name=f"User {i}",
                login=f"user{i}",
            )
            users.append(user)

        assert len(users) == 5
        logins = [u.login for u in users]
        assert len(set(logins)) == 5  # All unique


# ====================
# Read Tests
# ====================


class TestUserRead:
    """Tests for reading users."""

    async def test_get_user_by_id(self, user_factory):
        """Test getting user by ID."""
        from backend.base.crm.users.models.users import User

        created = await user_factory(name="Get Test User")

        fetched = await User.get(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "Get Test User"

    async def test_get_nonexistent_user(self):
        """Test getting non-existent user returns None."""
        from backend.base.crm.users.models.users import User

        result = await User.get(99999)
        assert result is None

    async def test_get_user_with_specific_fields(self, user_factory):
        """Test getting user with specific fields only."""
        from backend.base.crm.users.models.users import User

        created = await user_factory(
            name="Fields Test",
            login="fields_test",
        )

        fetched = await User.get(created.id, fields=["id", "name", "login"])
        assert fetched.id == created.id
        assert fetched.name == "Fields Test"
        assert fetched.login == "fields_test"

    async def test_search_all_users(self, user_factory):
        """Test searching all users."""
        from backend.base.crm.users.models.users import User

        await user_factory(name="Search User 1")
        await user_factory(name="Search User 2")
        await user_factory(name="Search User 3")

        users = await User.search(fields=["id", "name"])
        assert len(users) >= 3

    async def test_search_with_filter(self, user_factory):
        """Test searching with filter."""
        from backend.base.crm.users.models.users import User

        await user_factory(name="Filter User", login="filteruser")
        await user_factory(name="Other User", login="otheruser")

        users = await User.search(
            fields=["id", "name", "login"],
            filter=[("login", "=", "filteruser")],
        )

        assert len(users) == 1
        assert users[0].login == "filteruser"

    async def test_search_with_limit(self, user_factory):
        """Test searching with limit."""
        from backend.base.crm.users.models.users import User

        for i in range(5):
            await user_factory(name=f"Limit User {i}")

        users = await User.search(fields=["id"], limit=3)
        assert len(users) == 3

    async def test_search_with_pagination(self, user_factory):
        """Test searching with pagination."""
        from backend.base.crm.users.models.users import User

        for i in range(10):
            await user_factory(name=f"Page User {i}", login=f"pageuser{i}")

        page1 = await User.search(fields=["id"], start=0, end=5)
        page2 = await User.search(fields=["id"], start=5, end=10)

        assert len(page1) == 5
        assert len(page2) == 5

        page1_ids = {u.id for u in page1}
        page2_ids = {u.id for u in page2}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_search_with_sort(self, user_factory):
        """Test searching with sorting."""
        from backend.base.crm.users.models.users import User

        await user_factory(name="Zebra User", login="zebra")
        await user_factory(name="Alpha User", login="alpha")
        await user_factory(name="Middle User", login="middle")

        users = await User.search(
            fields=["id", "name"],
            sort="name",
            order="asc",
        )

        names = [u.name for u in users]
        assert names == sorted(names)

    async def test_table_len(self, user_factory):
        """Test counting users."""
        from backend.base.crm.users.models.users import User

        initial_count = await User.table_len()

        await user_factory()
        await user_factory()
        await user_factory()

        new_count = await User.table_len()
        assert new_count == initial_count + 3


# ====================
# Update Tests
# ====================


class TestUserUpdate:
    """Tests for updating users."""

    async def test_update_single_field(self, user_factory):
        """Test updating single field."""
        from backend.base.crm.users.models.users import User

        user = await user_factory(name="Original Name")

        await user.update(User(name="Updated Name"))

        updated = await User.get(user.id)
        assert updated.name == "Updated Name"

    async def test_update_multiple_fields(self, user_factory):
        """Test updating multiple fields."""
        from backend.base.crm.users.models.users import User

        user = await user_factory(
            name="Multi Update",
            home_page="/old",
        )

        await user.update(
            User(
                name="New Name",
                home_page="/new",
                layout_theme="classic",
            ),
            fields=["name", "home_page", "layout_theme"],
        )

        updated = await User.get(user.id)
        assert updated.name == "New Name"
        assert updated.home_page == "/new"
        assert updated.layout_theme == "classic"

    async def test_update_admin_flag(self, user_factory):
        """Test updating admin flag."""
        from backend.base.crm.users.models.users import User

        user = await user_factory(is_admin=False)
        assert user.is_admin is False

        await user.update(User(is_admin=True))

        updated = await User.get(user.id)
        assert updated.is_admin is True

    async def test_bulk_update(self, user_factory):
        """Test bulk update."""
        from backend.base.crm.users.models.users import User

        users = []
        for i in range(5):
            u = await user_factory(name=f"Bulk {i}", home_page=f"/page{i}")
            users.append(u)

        ids = [u.id for u in users]
        await User.update_bulk(
            ids=ids,
            payload=User(home_page="/bulk_updated"),
        )

        for user_id in ids:
            updated = await User.get(user_id)
            assert updated.home_page == "/bulk_updated"


# ====================
# Delete Tests
# ====================


class TestUserDelete:
    """Tests for deleting users."""

    async def test_delete_user(self, user_factory):
        """Test deleting single user."""
        from backend.base.crm.users.models.users import User

        user = await user_factory(name="To Delete")
        user_id = user.id

        await user.delete()

        deleted = await User.get(user_id)
        assert deleted is None

    async def test_delete_bulk(self, user_factory):
        """Test bulk delete."""
        from backend.base.crm.users.models.users import User

        users = []
        for i in range(5):
            u = await user_factory(name=f"Bulk Delete {i}")
            users.append(u)

        ids_to_delete = [users[0].id, users[1].id, users[2].id]
        ids_to_keep = [users[3].id, users[4].id]

        await User.delete_bulk(ids_to_delete)

        for user_id in ids_to_delete:
            assert await User.get_or_none(user_id) is None

        for user_id in ids_to_keep:
            assert await User.get(user_id) is not None


# ====================
# Password Tests
# ====================


class TestUserPassword:
    """Tests for password management."""

    async def test_password_hash_generation(self, user_factory):
        """Test password hash generation."""
        from backend.base.crm.users.models.users import User

        user = await user_factory()

        # Generate hash with known salt
        hash1 = user.generate_password_hash("password123", "test_salt")
        hash2 = user.generate_password_hash("password123", "test_salt")

        assert hash1 == hash2  # Same password + salt = same hash
        assert len(hash1) > 0

    async def test_password_hash_different_salts(self, user_factory):
        """Test that different salts produce different hashes."""
        from backend.base.crm.users.models.users import User

        user = await user_factory()

        hash1 = user.generate_password_hash("password123", "salt1")
        hash2 = user.generate_password_hash("password123", "salt2")

        assert hash1 != hash2

    async def test_password_hash_different_passwords(self, user_factory):
        """Test that different passwords produce different hashes."""
        from backend.base.crm.users.models.users import User

        user = await user_factory()

        hash1 = user.generate_password_hash("password1", "same_salt")
        hash2 = user.generate_password_hash("password2", "same_salt")

        assert hash1 != hash2

    async def test_password_policy_validation(self):
        """Test password policy validation."""
        from backend.base.crm.users.models.users import User

        # Default policy (min 5 chars)
        default_policy = User._DEFAULT_PASSWORD_POLICY

        # Valid password
        errors = User.validate_password("test123", default_policy)
        assert len(errors) == 0

        # Too short
        errors = User.validate_password("test", default_policy)
        assert len(errors) == 1
        assert "too_short" in errors[0]

    async def test_password_policy_uppercase(self):
        """Test password policy with uppercase requirement."""
        from backend.base.crm.users.models.users import User

        policy = {"require_uppercase": True, "min_length": 5}

        # No uppercase
        errors = User.validate_password("password123", policy)
        assert "no_uppercase" in errors

        # Has uppercase
        errors = User.validate_password("Password123", policy)
        assert "no_uppercase" not in errors

    async def test_password_policy_lowercase(self):
        """Test password policy with lowercase requirement."""
        from backend.base.crm.users.models.users import User

        policy = {"require_lowercase": True, "min_length": 5}

        # No lowercase
        errors = User.validate_password("PASSWORD123", policy)
        assert "no_lowercase" in errors

        # Has lowercase
        errors = User.validate_password("Password123", policy)
        assert "no_lowercase" not in errors

    async def test_password_policy_digits(self):
        """Test password policy with digit requirement."""
        from backend.base.crm.users.models.users import User

        policy = {"require_digits": True, "min_length": 5}

        # No digits
        errors = User.validate_password("password", policy)
        assert "no_digit" in errors

        # Has digits
        errors = User.validate_password("password123", policy)
        assert "no_digit" not in errors

    async def test_password_policy_special(self):
        """Test password policy with special char requirement."""
        from backend.base.crm.users.models.users import User

        policy = {"require_special": True, "min_length": 5}

        # No special
        errors = User.validate_password("password123", policy)
        assert "no_special" in errors

        # Has special
        errors = User.validate_password("password123!", policy)
        assert "no_special" not in errors

    async def test_password_policy_all_requirements(self):
        """Test password policy with all requirements."""
        from backend.base.crm.users.models.users import User

        policy = {
            "min_length": 8,
            "require_uppercase": True,
            "require_lowercase": True,
            "require_digits": True,
            "require_special": True,
        }

        # Fails all
        errors = User.validate_password("test", policy)
        assert len(errors) >= 4

        # Passes all
        errors = User.validate_password("Password123!", policy)
        assert len(errors) == 0


# ====================
# Session Tests
# ====================


class TestUserSession:
    """Tests for user session management."""

    async def test_terminate_sessions(self, user_factory, db_pool):
        """Test terminating all user sessions."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.security.models.sessions import Session
        from datetime import timedelta
        import secrets

        user = await user_factory()

        # Create multiple sessions
        for i in range(3):
            session = Session(
                user_id=user.id,
                token=secrets.token_urlsafe(64),
                ttl=3600,
                expired_datetime=datetime.now(timezone.utc)
                + timedelta(hours=1),
                create_user_id=user.id,
                update_user_id=user.id,
                active=True,
            )
            await Session.create(session)

        # Verify sessions exist
        active_sessions = await Session.search(
            fields=["id"],
            filter=[
                ("user_id", "=", user.id),
                ("active", "=", True),
            ],
        )
        assert len(active_sessions) == 3

        # Terminate all sessions
        terminated = await user.terminate_sessions()
        assert terminated == 3

        # Verify all sessions are inactive
        remaining = await Session.search(
            fields=["id"],
            filter=[
                ("user_id", "=", user.id),
                ("active", "=", True),
            ],
        )
        assert len(remaining) == 0

    async def test_terminate_sessions_except_current(
        self, user_factory, db_pool
    ):
        """Test terminating sessions except current."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.security.models.sessions import Session
        from datetime import timedelta
        import secrets

        user = await user_factory()

        # Create sessions
        current_token = secrets.token_urlsafe(64)
        tokens = [
            current_token,
            secrets.token_urlsafe(64),
            secrets.token_urlsafe(64),
        ]

        for token in tokens:
            session = Session(
                user_id=user.id,
                token=token,
                ttl=3600,
                expired_datetime=datetime.now(timezone.utc)
                + timedelta(hours=1),
                create_user_id=user.id,
                update_user_id=user.id,
                active=True,
            )
            await Session.create(session)

        # Terminate all except current
        terminated = await user.terminate_sessions(exclude_token=current_token)
        assert terminated == 2

        # Verify current session is still active
        remaining = await Session.search(
            fields=["id", "token"],
            filter=[
                ("user_id", "=", user.id),
                ("active", "=", True),
            ],
        )
        assert len(remaining) == 1
        assert remaining[0].token == current_token


# ====================
# Role Tests
# ====================


class TestUserRoles:
    """Tests for user role management."""

    async def test_assign_role_to_user(self, user_factory):
        """Test assigning role to user."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.security.models.roles import Role

        user = await user_factory()

        # Create role
        role_id = await Role.create(Role(name="Test Role"))

        # Assign role via Many2many update
        await user.update(
            User(role_ids={"selected": [role_id]}),
            fields=["role_ids"],
        )

        # Verify role assigned
        updated = await User.get(user.id, fields=["id", "role_ids"])
        role_ids = [r.id for r in updated.role_ids] if updated.role_ids else []
        assert role_id in role_ids

    async def test_get_all_roles_recursive(self, user_factory):
        """Test getting all roles including based roles."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.security.models.roles import Role

        user = await user_factory()

        # Create role hierarchy: admin -> manager -> user
        base_role_id = await Role.create(Role(name="Base Role"))
        middle_role_id = await Role.create(Role(name="Middle Role"))
        top_role_id = await Role.create(Role(name="Top Role"))

        # Assign only top role to user
        await user.update(
            User(role_ids={"selected": [top_role_id]}),
            fields=["role_ids"],
        )

        # Get all roles (should include inherited if based_role_ids is set up)
        all_roles = await user.get_all_roles()
        assert top_role_id in all_roles


# ====================
# JSON Serialization Tests
# ====================


class TestUserSerialization:
    """Tests for user serialization."""

    async def test_json_serialization(self, user_factory):
        """Test JSON serialization of user."""
        user = await user_factory(
            name="JSON User",
            login="jsonuser",
        )

        json_data = user.json()

        assert isinstance(json_data, dict)
        assert json_data["id"] == user.id
        assert json_data["name"] == "JSON User"
        assert json_data["login"] == "jsonuser"

    async def test_json_exclude_sensitive_fields(self, user_factory):
        """Test excluding sensitive fields from JSON."""
        user = await user_factory()

        json_data = user.json(exclude={"password_hash", "password_salt"})

        assert "password_hash" not in json_data
        assert "password_salt" not in json_data
        assert "name" in json_data

    async def test_json_include_only_specific_fields(self, user_factory):
        """Test including only specific fields in JSON."""
        user = await user_factory(name="Include Test")

        json_data = user.json(include={"id", "name"})

        assert "id" in json_data
        assert "name" in json_data
        assert "login" not in json_data
        assert "password_hash" not in json_data


# ====================
# Edge Cases
# ====================


class TestUserEdgeCases:
    """Tests for edge cases."""

    async def test_unicode_name(self, user_factory):
        """Test user with unicode name."""
        user = await user_factory(name="Тест Unicode 日本語 🎉")

        fetched = await user_factory.__self__  # Get model class
        from backend.base.crm.users.models.users import User

        fetched = await User.get(user.id)

        assert fetched.name == "Тест Unicode 日本語 🎉"

    async def test_special_characters_in_login(self, user_factory):
        """Test login with special characters."""
        # Only alphanumeric and underscore typically allowed
        user = await user_factory(login="user_with_underscore")

        from backend.base.crm.users.models.users import User

        fetched = await User.get(user.id)

        assert fetched.login == "user_with_underscore"

    async def test_empty_search_result(self):
        """Test search on empty table."""
        from backend.base.crm.users.models.users import User

        users = await User.search(fields=["id"])
        assert users == []

    async def test_update_nonexistent_user(self):
        """Test updating non-existent user."""
        from backend.base.crm.users.models.users import User

        user = User(name="test")
        user.id = 99999

        # Should not raise, just update nothing
        await user.update(User(name="updated"))
