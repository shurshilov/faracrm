"""
Integration tests for Security module.

Tests cover:
- Role CRUD
- AccessList (ACL) management
- Rules management
- Session management
- Permission checks

Run: pytest tests/integration/security/test_security.py -v -m integration
"""

import pytest
from datetime import datetime, timedelta, timezone

pytestmark = pytest.mark.integration


# ====================
# Role Tests
# ====================


class TestRoles:
    """Tests for Role model."""

    async def test_create_role(self):
        """Test creating a role."""
        from backend.base.crm.security.models.roles import Role

        role_id = await Role.create(Role(name="Admin"))

        assert role_id > 0

        role = await Role.get(role_id)
        assert role.name == "Admin"

    async def test_create_role_with_model(self):
        """Test creating role with associated model."""
        from backend.base.crm.security.models.roles import Role
        from backend.base.crm.security.models.models import Model

        model_id = await Model.create(
            Model(
                name="users", model="backend.base.crm.users.models.users.User"
            )
        )

        role_id = await Role.create(
            Role(
                name="User Manager",
                model_id=model_id,
            )
        )

        role = await Role.get(role_id, fields=["id", "name", "model_id"])
        assert role.model_id.id == model_id

    async def test_assign_users_to_role(self, user_factory):
        """Test assigning users to role via Many2many."""
        from backend.base.crm.security.models.roles import Role
        from backend.base.crm.users.models.users import User

        user1 = await user_factory(name="Role User 1", login="role_user1")
        user2 = await user_factory(name="Role User 2", login="role_user2")

        role_id = await Role.create(Role(name="Test Role"))
        role = await Role.get(role_id)

        # Assign users
        await role.update(
            Role(user_ids={"selected": [user1.id, user2.id]}),
            fields=["user_ids"],
        )

        # Verify
        updated = await Role.get(role_id, fields=["id", "user_ids"])
        user_ids = [u.id for u in updated.user_ids] if updated.user_ids else []
        assert user1.id in user_ids
        assert user2.id in user_ids

    async def test_search_roles(self):
        """Test searching roles."""
        from backend.base.crm.security.models.roles import Role

        await Role.create(Role(name="Role A"))
        await Role.create(Role(name="Role B"))
        await Role.create(Role(name="Role C"))

        roles = await Role.search(fields=["id", "name"])
        assert len(roles) >= 3

    async def test_delete_role(self):
        """Test deleting role."""
        from backend.base.crm.security.models.roles import Role

        role_id = await Role.create(Role(name="To Delete"))
        role = await Role.get(role_id)

        await role.delete()

        deleted = await Role.get(role_id)
        assert deleted is None


# ====================
# AccessList (ACL) Tests
# ====================


class TestAccessList:
    """Tests for AccessList (ACL) model."""

    async def test_create_acl(self):
        """Test creating ACL."""
        from backend.base.crm.security.models.acls import AccessList
        from backend.base.crm.security.models.roles import Role
        from backend.base.crm.security.models.models import Model

        model_id = await Model.create(
            Model(
                name="partners",
                model="backend.base.crm.partners.models.partners.Partner",
            )
        )
        role_id = await Role.create(Role(name="Partner Manager"))

        acl_id = await AccessList.create(
            AccessList(
                name="Partner Full Access",
                model_id=model_id,
                role_id=role_id,
                perm_create=True,
                perm_read=True,
                perm_update=True,
                perm_delete=True,
                active=True,
            )
        )

        acl = await AccessList.get(acl_id)
        assert acl.name == "Partner Full Access"
        assert acl.perm_create is True
        assert acl.perm_read is True
        assert acl.perm_update is True
        assert acl.perm_delete is True

    async def test_create_read_only_acl(self):
        """Test creating read-only ACL."""
        from backend.base.crm.security.models.acls import AccessList
        from backend.base.crm.security.models.roles import Role
        from backend.base.crm.security.models.models import Model

        model_id = await Model.create(Model(name="reports", model="reports"))
        role_id = await Role.create(Role(name="Viewer"))

        acl_id = await AccessList.create(
            AccessList(
                name="Reports Read Only",
                model_id=model_id,
                role_id=role_id,
                perm_create=False,
                perm_read=True,
                perm_update=False,
                perm_delete=False,
                active=True,
            )
        )

        acl = await AccessList.get(acl_id)
        assert acl.perm_create is False
        assert acl.perm_read is True
        assert acl.perm_update is False
        assert acl.perm_delete is False

    async def test_acl_default_inactive(self):
        """Test ACL default values."""
        from backend.base.crm.security.models.acls import AccessList

        acl_id = await AccessList.create(AccessList(name="Default ACL"))

        acl = await AccessList.get(acl_id)
        assert acl.active is False  # Default
        assert acl.perm_create is False
        assert acl.perm_read is False

    async def test_search_acls_by_role(self):
        """Test searching ACLs by role."""
        from backend.base.crm.security.models.acls import AccessList
        from backend.base.crm.security.models.roles import Role

        role1_id = await Role.create(Role(name="Role 1"))
        role2_id = await Role.create(Role(name="Role 2"))

        await AccessList.create(AccessList(name="ACL 1", role_id=role1_id))
        await AccessList.create(AccessList(name="ACL 2", role_id=role1_id))
        await AccessList.create(AccessList(name="ACL 3", role_id=role2_id))

        acls = await AccessList.search(
            fields=["id", "name"],
            filter=[("role_id", "=", role1_id)],
        )

        assert len(acls) == 2


# ====================
# Rule Tests
# ====================


class TestRules:
    """Tests for Rule model."""

    async def test_create_rule(self):
        """Test creating rule."""
        from backend.base.crm.security.models.rules import Rule
        from backend.base.crm.security.models.roles import Role

        role_id = await Role.create(Role(name="Rule Test Role"))

        rule_id = await Rule.create(
            Rule(
                name="See Own Records Only",
                role_id=role_id,
                domain_force="[('user_id', '=', user.id)]",
            )
        )

        rule = await Rule.get(rule_id)
        assert rule.name == "See Own Records Only"
        assert rule.domain_force == "[('user_id', '=', user.id)]"

    async def test_search_rules_by_role(self):
        """Test searching rules by role."""
        from backend.base.crm.security.models.rules import Rule
        from backend.base.crm.security.models.roles import Role

        role_id = await Role.create(Role(name="Rules Role"))

        await Rule.create(Rule(name="Rule 1", role_id=role_id))
        await Rule.create(Rule(name="Rule 2", role_id=role_id))

        rules = await Rule.search(
            fields=["id", "name"],
            filter=[("role_id", "=", role_id)],
        )

        assert len(rules) == 2


# ====================
# Session Tests
# ====================


class TestSessions:
    """Tests for Session model."""

    async def test_create_session(self, user_factory):
        """Test creating session."""
        from backend.base.crm.security.models.sessions import Session
        import secrets

        user = await user_factory()
        token = secrets.token_urlsafe(64)

        session_id = await Session.create(
            Session(
                user_id=user.id,
                token=token,
                ttl=3600,
                expired_datetime=datetime.now(timezone.utc)
                + timedelta(hours=1),
                create_user_id=user.id,
                update_user_id=user.id,
                active=True,
            )
        )

        session = await Session.get(session_id)
        assert session.token == token
        assert session.active is True

    async def test_session_expiration(self, user_factory):
        """Test session expiration check."""
        from backend.base.crm.security.models.sessions import Session
        import secrets

        user = await user_factory()

        # Create expired session
        expired_token = secrets.token_urlsafe(64)
        await Session.create(
            Session(
                user_id=user.id,
                token=expired_token,
                ttl=3600,
                expired_datetime=datetime.now(timezone.utc)
                - timedelta(hours=1),  # Past
                create_user_id=user.id,
                update_user_id=user.id,
                active=True,
            )
        )

        # Create valid session
        valid_token = secrets.token_urlsafe(64)
        valid_id = await Session.create(
            Session(
                user_id=user.id,
                token=valid_token,
                ttl=3600,
                expired_datetime=datetime.now(timezone.utc)
                + timedelta(hours=1),  # Future
                create_user_id=user.id,
                update_user_id=user.id,
                active=True,
            )
        )

        # Search for non-expired sessions
        sessions = await Session.search(
            fields=["id", "token"],
            filter=[
                ("user_id", "=", user.id),
                ("active", "=", True),
                ("expired_datetime", ">", datetime.now(timezone.utc)),
            ],
        )

        # Only valid session should be returned
        tokens = [s.token for s in sessions]
        assert valid_token in tokens
        assert expired_token not in tokens

    async def test_deactivate_session(self, user_factory):
        """Test deactivating session."""
        from backend.base.crm.security.models.sessions import Session
        import secrets

        user = await user_factory()
        token = secrets.token_urlsafe(64)

        session_id = await Session.create(
            Session(
                user_id=user.id,
                token=token,
                ttl=3600,
                expired_datetime=datetime.now(timezone.utc)
                + timedelta(hours=1),
                create_user_id=user.id,
                update_user_id=user.id,
                active=True,
            )
        )

        session = await Session.get(session_id)
        await session.update(Session(active=False))

        updated = await Session.get(session_id)
        assert updated.active is False

    async def test_find_session_by_token(self, user_factory):
        """Test finding session by token."""
        from backend.base.crm.security.models.sessions import Session
        import secrets

        user = await user_factory()
        token = secrets.token_urlsafe(64)

        await Session.create(
            Session(
                user_id=user.id,
                token=token,
                ttl=3600,
                expired_datetime=datetime.now(timezone.utc)
                + timedelta(hours=1),
                create_user_id=user.id,
                update_user_id=user.id,
                active=True,
            )
        )

        sessions = await Session.search(
            fields=["id", "user_id", "token"],
            filter=[("token", "=", token)],
        )

        assert len(sessions) == 1
        assert sessions[0].token == token


# ====================
# Model Tests
# ====================


class TestModels:
    """Tests for Model registry."""

    async def test_create_model(self):
        """Test creating model entry."""
        from backend.base.crm.security.models.models import Model

        model_id = await Model.create(
            Model(
                name="sales",
                model="backend.base.crm.sales.models.sale.Sale",
            )
        )

        model = await Model.get(model_id)
        assert model.name == "sales"

    async def test_search_models(self):
        """Test searching models."""
        from backend.base.crm.security.models.models import Model

        await Model.create(Model(name="model_a", model="model_a"))
        await Model.create(Model(name="model_b", model="model_b"))

        models = await Model.search(fields=["id", "name"])
        assert len(models) >= 2


# ====================
# App Tests
# ====================


class TestApps:
    """Tests for App model."""

    async def test_create_app(self):
        """Test creating app entry."""
        from backend.base.crm.security.models.apps import App

        app_id = await App.create(
            App(
                name="CRM",
                sequence=10,
            )
        )

        app = await App.get(app_id)
        assert app.name == "CRM"
        assert app.sequence == 10

    async def test_search_apps_ordered(self):
        """Test searching apps with ordering."""
        from backend.base.crm.security.models.apps import App

        await App.create(App(name="App C", sequence=30))
        await App.create(App(name="App A", sequence=10))
        await App.create(App(name="App B", sequence=20))

        apps = await App.search(
            fields=["id", "name", "sequence"],
            sort="sequence",
            order="asc",
        )

        sequences = [a.sequence for a in apps]
        assert sequences == sorted(sequences)


# ====================
# Integration Tests
# ====================


class TestSecurityIntegration:
    """Integration tests for security system."""

    async def test_full_permission_setup(self, user_factory):
        """Test complete permission setup flow."""
        from backend.base.crm.security.models.roles import Role
        from backend.base.crm.security.models.acls import AccessList
        from backend.base.crm.security.models.rules import Rule
        from backend.base.crm.security.models.models import Model
        from backend.base.crm.users.models.users import User

        # 1. Create model
        model_id = await Model.create(
            Model(
                name="leads",
                model="backend.base.crm.leads.models.leads.Lead",
            )
        )

        # 2. Create role
        role_id = await Role.create(Role(name="Sales Rep"))

        # 3. Create ACL
        acl_id = await AccessList.create(
            AccessList(
                name="Leads Access",
                model_id=model_id,
                role_id=role_id,
                perm_create=True,
                perm_read=True,
                perm_update=True,
                perm_delete=False,  # Can't delete
                active=True,
            )
        )

        # 4. Create rule (see own records only)
        rule_id = await Rule.create(
            Rule(
                name="Own Leads Only",
                role_id=role_id,
                domain_force="[('user_id', '=', user.id)]",
            )
        )

        # 5. Create user and assign role
        user = await user_factory(name="Sales Person", login="sales")
        await user.update(
            User(role_ids={"selected": [role_id]}),
            fields=["role_ids"],
        )

        # Verify setup
        role = await Role.get(role_id, fields=["id", "user_ids", "acl_ids"])
        user_ids = [u.id for u in role.user_ids] if role.user_ids else []
        assert user.id in user_ids

        acl_list = [a.id for a in role.acl_ids] if role.acl_ids else []
        assert acl_id in acl_list

    async def test_user_multiple_roles(self, user_factory):
        """Test user with multiple roles."""
        from backend.base.crm.security.models.roles import Role
        from backend.base.crm.users.models.users import User

        # Create roles
        admin_role_id = await Role.create(Role(name="Admin"))
        editor_role_id = await Role.create(Role(name="Editor"))
        viewer_role_id = await Role.create(Role(name="Viewer"))

        # Create user with multiple roles
        user = await user_factory(name="Multi Role User")
        await user.update(
            User(
                role_ids={
                    "selected": [admin_role_id, editor_role_id, viewer_role_id]
                }
            ),
            fields=["role_ids"],
        )

        # Verify
        updated = await User.get(user.id, fields=["id", "role_ids"])
        role_ids = [r.id for r in updated.role_ids] if updated.role_ids else []

        assert admin_role_id in role_ids
        assert editor_role_id in role_ids
        assert viewer_role_id in role_ids
        assert len(role_ids) == 3
