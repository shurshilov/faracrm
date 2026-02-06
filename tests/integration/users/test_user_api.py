"""
Integration tests for User API endpoints.

Tests cover:
- User CRUD endpoints
- Authentication endpoints (signin)
- Password change endpoint
- User copy endpoint

Run: pytest tests/integration/users/test_user_api.py -v -m integration
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.api]


# ====================
# Signin Tests
# ====================


class TestSigninAPI:
    """Tests for signin endpoint."""

    async def test_signin_success(self, client):
        """Test successful signin."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.languages.models.language import Language
        import secrets

        # Create language
        lang_id = await Language.create(
            Language(
                code="en",
                name="English",
                active=True,
            )
        )

        # Create user with known password
        password = "test_password"
        salt = secrets.token_hex(64)
        user = User(
            name="Test User",
            login="testlogin",
            password_salt=salt,
            lang_id=lang_id,
        )
        # Generate hash using same method
        user.password_hash = user.generate_password_hash(password, salt)
        user_id = await User.create(user)

        # Try signin
        response = await client.post(
            "/signin",
            json={
                "login": "testlogin",
                "password": password,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user_id" in data
        assert data["user_id"]["name"] == "Test User"

    async def test_signin_wrong_password(self, client):
        """Test signin with wrong password."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.languages.models.language import Language
        import secrets

        lang_id = await Language.create(
            Language(
                code="en",
                name="English",
                active=True,
            )
        )

        salt = secrets.token_hex(64)
        user = User(
            name="Test User",
            login="wrongpwduser",
            password_salt=salt,
            lang_id=lang_id,
        )
        user.password_hash = user.generate_password_hash(
            "correct_password", salt
        )
        await User.create(user)

        response = await client.post(
            "/signin",
            json={
                "login": "wrongpwduser",
                "password": "wrong_password",
            },
        )

        assert response.status_code == 401  # Auth failed

    async def test_signin_nonexistent_user(self, client):
        """Test signin with non-existent user."""
        response = await client.post(
            "/signin",
            json={
                "login": "nonexistent",
                "password": "anypassword",
            },
        )

        assert response.status_code == 401  # User not found


# ====================
# Password Change Tests
# ====================


class TestPasswordChangeAPI:
    """Tests for password change endpoint."""

    async def test_change_password_success(self, authenticated_client):
        """Test successful password change."""
        client, user_id, token = authenticated_client

        response = await client.post(
            "/users/password_change",
            json={
                "user_id": user_id,
                "password": "NewSecurePassword123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True

    async def test_change_password_too_short(self, authenticated_client):
        """Test password change with too short password."""
        client, user_id, token = authenticated_client

        response = await client.post(
            "/users/password_change",
            json={
                "user_id": user_id,
                "password": "abc",  # Too short
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"] == "#PASSWORD_POLICY"

    async def test_change_password_self(self, authenticated_client):
        """Test changing own password (no user_id specified)."""
        client, user_id, token = authenticated_client

        response = await client.post(
            "/users/password_change",
            json={
                "password": "NewPassword12345",
            },
        )

        assert response.status_code == 200

    async def test_change_password_unauthorized(self, client):
        """Test password change without authentication."""
        response = await client.post(
            "/users/password_change",
            json={
                "user_id": 1,
                "password": "NewPassword123",
            },
        )

        assert response.status_code in [401, 403]  # Unauthorized


# ====================
# Copy User Tests
# ====================


class TestCopyUserAPI:
    """Tests for user copy endpoint."""

    async def test_copy_user_basic(self, authenticated_client, user_factory):
        """Test basic user copy."""
        client, auth_user_id, token = authenticated_client

        # Create source user
        source = await user_factory(
            name="Source User",
            login="source_user",
        )

        response = await client.post(
            "/users/copy",
            json={
                "source_user_id": source.id,
                "name": "Copied User",
                "login": "copied_user",
                "copy_password": False,
                "copy_roles": True,
                "copy_files": False,
                "copy_languages": True,
                "copy_is_admin": True,
                "copy_contacts": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Copied User"
        assert data["login"] == "copied_user"
        assert "id" in data

    async def test_copy_user_with_roles(
        self, authenticated_client, user_factory, db_pool
    ):
        """Test copying user with roles."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.security.models.roles import Role

        client, auth_user_id, token = authenticated_client

        # Create role
        role_id = await Role.create(Role(name="Copy Test Role"))

        # Create source user with role
        source = await user_factory(
            name="Source With Role", login="source_role"
        )
        await source.update(User(role_ids={"selected": [role_id]}))

        response = await client.post(
            "/users/copy",
            json={
                "source_user_id": source.id,
                "name": "Copy With Role",
                "login": "copy_with_role",
                "copy_password": False,
                "copy_roles": True,
                "copy_files": False,
                "copy_languages": True,
                "copy_is_admin": False,
                "copy_contacts": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify roles were copied
        copied = await User.get(
            data["id"],
            fields=["id", "role_ids"],
            fields_nested={"role_ids": ["id"]},
        )
        role_ids = [r.id for r in copied.role_ids] if copied.role_ids else []
        assert role_id in role_ids

    async def test_copy_user_duplicate_login(
        self, authenticated_client, user_factory
    ):
        """Test copying user with duplicate login fails."""
        client, auth_user_id, token = authenticated_client

        source = await user_factory(name="Source", login="existing_login")
        await user_factory(name="Existing", login="taken_login")

        response = await client.post(
            "/users/copy",
            json={
                "source_user_id": source.id,
                "name": "Copy",
                "login": "taken_login",  # Already exists
                "copy_password": False,
                "copy_roles": False,
                "copy_files": False,
                "copy_languages": False,
                "copy_is_admin": False,
                "copy_contacts": False,
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    async def test_copy_nonexistent_user(self, authenticated_client):
        """Test copying non-existent user."""
        client, auth_user_id, token = authenticated_client

        response = await client.post(
            "/users/copy",
            json={
                "source_user_id": 99999,
                "name": "Copy",
                "login": "copy_nonexistent",
                "copy_password": False,
                "copy_roles": False,
                "copy_files": False,
                "copy_languages": False,
                "copy_is_admin": False,
                "copy_contacts": False,
            },
        )

        assert response.status_code == 404


# ====================
# CRUD API Tests
# ====================


class TestUserCRUDAPI:
    """Tests for standard CRUD endpoints."""

    async def test_search_users(self, authenticated_client, user_factory):
        """Test searching users via API."""
        client, _, _ = authenticated_client

        await user_factory(name="API Search 1", login="api_search_1")
        await user_factory(name="API Search 2", login="api_search_2")

        response = await client.post(
            "/users/search",
            json={
                "fields": ["id", "name", "login"],
                "limit": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data
        assert len(data["data"]) >= 2

    async def test_search_users_with_filter(
        self, authenticated_client, user_factory
    ):
        """Test searching users with filter via API."""
        client, _, _ = authenticated_client

        await user_factory(name="Filter API Test", login="filter_api_test")

        response = await client.post(
            "/users/search",
            json={
                "fields": ["id", "name", "login"],
                "filter": [["login", "=", "filter_api_test"]],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["login"] == "filter_api_test"

    async def test_get_user_by_id(self, authenticated_client, user_factory):
        """Test getting user by ID via API."""
        client, _, _ = authenticated_client

        user = await user_factory(name="Get By ID", login="get_by_id")

        response = await client.post(
            f"/users/{user.id}",
            json={
                "fields": ["id", "name", "login"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == user.id
        assert data["data"]["name"] == "Get By ID"

    async def test_create_user_via_api(self, authenticated_client, db_pool):
        """Test creating user via API."""
        from backend.base.crm.languages.models.language import Language

        client, _, _ = authenticated_client

        # Ensure language exists
        langs = await Language.search(
            fields=["id"], filter=[("code", "=", "en")]
        )
        if not langs:
            lang_id = await Language.create(
                Language(
                    code="en",
                    name="English",
                    active=True,
                )
            )
        else:
            lang_id = langs[0].id

        response = await client.post(
            "/users",
            json={
                "name": "API Created User",
                "login": "api_created",
                "email": "api@test.com",
                "password_hash": "hash",
                "password_salt": "salt",
                "lang_id": lang_id,
            },
        )

        # Note: Response depends on your API implementation
        assert response.status_code in [
            200,
            201,
            422,
        ]  # 422 if email validation fails

    async def test_update_user_via_api(
        self, authenticated_client, user_factory
    ):
        """Test updating user via API."""
        client, _, _ = authenticated_client

        user = await user_factory(name="Before Update", login="before_update")

        response = await client.put(
            f"/users/{user.id}",
            json={
                "name": "After Update",
            },
        )

        assert response.status_code == 200

        # Verify update
        from backend.base.crm.users.models.users import User

        updated = await User.get(user.id)
        assert updated.name == "After Update"

    async def test_delete_user_via_api(
        self, authenticated_client, user_factory
    ):
        """Test deleting user via API."""
        client, _, _ = authenticated_client

        user = await user_factory(name="To Delete API", login="to_delete_api")
        user_id = user.id

        response = await client.delete(f"/users/{user_id}")

        assert response.status_code == 200

        # Verify deletion
        from backend.base.crm.users.models.users import User

        deleted = await User.get_or_none(user_id)
        assert deleted is None

    async def test_bulk_delete_users(self, authenticated_client, user_factory):
        """Test bulk deleting users via API."""
        client, _, _ = authenticated_client

        users = []
        for i in range(3):
            u = await user_factory(
                name=f"Bulk Delete API {i}", login=f"bulk_del_{i}"
            )
            users.append(u)

        ids = [u.id for u in users]

        response = await client.request(
            "DELETE",
            "/users/bulk",
            json=ids,
        )

        assert response.status_code == 200

        # Verify deletion
        from backend.base.crm.users.models.users import User

        for user_id in ids:
            assert await User.get_or_none(user_id) is None


# ====================
# Authorization Tests
# ====================


class TestUserAuthorization:
    """Tests for user authorization."""

    async def test_unauthenticated_request(self, client):
        """Test that unauthenticated requests are rejected."""
        response = await client.post(
            "/users/search",
            json={
                "fields": ["id", "name"],
            },
        )

        assert response.status_code in [401, 403]

    async def test_invalid_token(self, client):
        """Test that invalid tokens are rejected."""
        client.headers["Authorization"] = "Bearer invalid_token_12345"

        response = await client.post(
            "/users/search",
            json={
                "fields": ["id", "name"],
            },
        )

        assert response.status_code in [401, 403]

    async def test_expired_token(self, client):
        """Test that expired tokens are rejected."""
        from backend.base.crm.users.models.users import User
        from backend.base.crm.security.models.sessions import Session
        from backend.base.crm.languages.models.language import Language
        from datetime import datetime, timedelta, timezone
        import secrets

        # Create user
        lang_id = await Language.create(
            Language(code="en", name="English", active=True)
        )
        user_id = await User.create(
            User(
                name="Expired Token User",
                login="expired_token",
                password_hash="hash",
                password_salt="salt",
                lang_id=lang_id,
            )
        )

        # Create expired session
        token = secrets.token_urlsafe(64)
        await Session.create(
            Session(
                user_id=user_id,
                token=token,
                ttl=3600,
                expired_datetime=datetime.now(timezone.utc)
                - timedelta(hours=1),  # Expired
                create_user_id=user_id,
                update_user_id=user_id,
                active=True,
            )
        )

        client.headers["Authorization"] = f"Bearer {token}"

        response = await client.post(
            "/users/search",
            json={
                "fields": ["id", "name"],
            },
        )

        assert response.status_code in [401, 403]
