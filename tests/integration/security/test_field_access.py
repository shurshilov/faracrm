"""
Integration tests for FIELD-level access control (role_* attributes).

Third axis of access control on top of ACL (table) and Rules (row):
who may write a specific field. Guards against privilege escalation via
mass-assignment — e.g. an ordinary user assigning themselves a powerful
role (role_ids) or superuser flag (is_admin).

Mechanism under test:
- User.role_ids   → role_update="system_admin"
- User.is_admin   → role_create/role_update=SUPERUSER  (only superuser)
- Enforced in ORM create / update / update_bulk via
  AccessMixin._check_field_access → SecurityAccessChecker.check_field_access

The seeded access model (see users/app.py) makes the isolation clean:
- base_user: ACL update=True on `user` + rule "edit only own profile",
  so a base user genuinely passes ACL+Rules on their OWN record — any
  denial of role_ids there comes from the FIELD check, not table/row.
- system_admin: ACL.FULL on `user` — can create/update users, so denial
  of is_admin (superuser-only) isolates the field check.

Run: pytest tests/integration/security/test_field_access.py -v -m integration
"""

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration

from backend.base.system.dotorm.dotorm.access import (
    AccessDenied,
    set_access_session,
    get_access_session,
)
from backend.base.crm.users.models.users import User
from backend.base.crm.security.models.sessions import Session
from backend.base.system.core.exceptions.environment import FaraException

# ============================================================================
# Helpers (mirrors test_security_rules.py)
# ============================================================================


async def _make_session(user) -> Session:
    """Build a Session-like object — enough for AccessChecker.

    Carries EXPANDED roles (id + code) and teams exactly as the real
    session build (Session.session_check) does. Both the ACL check and the
    field-level checker read them straight from the session (no DB
    fallback), so test sessions must carry them too.
    """
    session = Session(
        id=0,
        active=True,
        user_id=user,
        token="test-token",
        ttl=3600,
    )
    Session._set_role_codes(session, await User.get_all_role_codes(user.id))
    Session._set_team_ids(session, await User.get_all_team_ids(user.id))
    return session


class as_user:
    """Async context manager: temporarily switch access_session to `user`."""

    def __init__(self, user):
        self.user = user
        self._prev = None

    async def __aenter__(self):
        self._prev = get_access_session()
        set_access_session(await _make_session(self.user))
        return self._prev

    async def __aexit__(self, *exc):
        set_access_session(self._prev)


async def _role_id(code: str) -> int:
    from backend.base.crm.security.models.roles import Role

    roles = await Role.search(
        filter=[("code", "=", code)], fields=["id"], limit=1
    )
    assert roles, f"role {code!r} must be seeded by post_init"
    return roles[0].id


async def _user_role_codes(user_id: int) -> set[str]:
    """Read a user's linked role codes (System session — free read)."""
    u = await User.get(
        user_id,
        fields=["id", "role_ids"],
        fields_nested={"role_ids": {"fields": ["id", "code"]}},
    )
    return {r.code for r in (u.role_ids or [])}


# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def base_role_id():
    return await _role_id("base_user")


@pytest_asyncio.fixture
async def system_admin_role_id():
    return await _role_id("system_admin")


@pytest_asyncio.fixture
async def alice(user_factory, base_role_id):
    """Ordinary internal user (base_user role)."""
    return await user_factory(
        name="Alice",
        login="alice",
        role_ids={"selected": [base_role_id]},
    )


@pytest_asyncio.fixture
async def target(user_factory, base_role_id):
    """Another ordinary user to be edited by others."""
    return await user_factory(
        name="Target",
        login="target",
        role_ids={"selected": [base_role_id]},
    )


@pytest_asyncio.fixture
async def sysadmin(user_factory, system_admin_role_id):
    """Settings administrator (system_admin role, NOT is_admin)."""
    return await user_factory(
        name="SysAdmin",
        login="sysadmin",
        role_ids={"selected": [system_admin_role_id]},
    )


@pytest_asyncio.fixture
async def superuser(user_factory):
    """Superuser (is_admin=True) — bypasses all checks."""
    return await user_factory(name="Root", login="root", is_admin=True)


# ============================================================================
# role_ids — the original vulnerability
# ============================================================================


class TestRoleIdsWrite:
    async def test_base_user_cannot_self_assign_role(
        self, alice, system_admin_role_id
    ):
        """The reported bug: base user grants themselves system_admin.

        ACL(update)+Rule(own profile) PASS — denial must come from the
        field-level check on role_ids.
        """
        async with as_user(alice):
            with pytest.raises(AccessDenied):
                await alice.update(
                    User(role_ids={"selected": [system_admin_role_id]})
                )

        # And it really did not get linked.
        assert "system_admin" not in await _user_role_codes(alice.id)

    async def test_base_user_can_edit_own_profile(self, alice):
        """Regression guard: normal profile edit (no role_ids) still works."""
        async with as_user(alice):
            await alice.update(User(name="Alice Renamed"))

        refreshed = await User.get(alice.id, fields=["id", "name"])
        assert refreshed.name == "Alice Renamed"

    async def test_system_admin_can_assign_roles(
        self, sysadmin, target, system_admin_role_id
    ):
        """system_admin is allowed to manage user roles."""
        async with as_user(sysadmin):
            await target.update(
                User(role_ids={"selected": [system_admin_role_id]})
            )

        assert "system_admin" in await _user_role_codes(target.id)


# ============================================================================
# is_admin — superuser-only field (SUPERUSER sentinel)
# ============================================================================


class TestIsAdminWrite:
    async def test_system_admin_cannot_create_superuser(self, sysadmin):
        """system_admin may create users (ACL.FULL) but NOT a superuser."""
        async with as_user(sysadmin):
            with pytest.raises(AccessDenied):
                await User.create(
                    User(
                        name="Hacker",
                        login="hacker_admin",
                        is_admin=True,
                        password_hash="h",
                        password_salt="s",
                    )
                )

    async def test_system_admin_can_create_normal_user(self, sysadmin):
        """Creating a user WITHOUT sending is_admin succeeds for system_admin.

        Presence-based: the client must omit restricted fields it can't set
        (frontend doesn't render is_admin for non-superusers); the field
        defaults to False server-side.
        """
        async with as_user(sysadmin):
            new_id = await User.create(
                User(
                    name="Normal",
                    login="normal_user",
                    password_hash="h",
                    password_salt="s",
                )
            )
        assert isinstance(new_id, int)

    async def test_system_admin_cannot_bulk_promote_admin(
        self, sysadmin, target
    ):
        """Closes the update_bulk hole. Now guarded in User.update_bulk
        (FaraException), with the field-level check as backstop — accept
        either."""
        async with as_user(sysadmin):
            with pytest.raises((FaraException, AccessDenied)):
                await User.update_bulk([target.id], User(is_admin=True))

        refreshed = await User.get(target.id, fields=["id", "is_admin"])
        assert refreshed.is_admin is False


# ============================================================================
# Superuser bypass
# ============================================================================


class TestSuperuserBypass:
    async def test_admin_can_set_role_and_admin(
        self, superuser, target, system_admin_role_id
    ):
        """is_admin (full access) bypasses every field-level restriction."""
        async with as_user(superuser):
            await target.update(
                User(
                    is_admin=True,
                    role_ids={"selected": [system_admin_role_id]},
                )
            )

        refreshed = await User.get(target.id, fields=["id", "is_admin"])
        assert refreshed.is_admin is True
        assert "system_admin" in await _user_role_codes(target.id)


# ============================================================================
# Source of role codes: the session (no DB fallback)
# ============================================================================


class TestRoleCodeSource:
    """check_field_access reads expanded role codes straight from the
    session (hydrated at session build) — there is no DB fallback. These
    pin both the hydrated path and the empty-session path."""

    async def test_reads_codes_from_session(self, alice, system_admin_role_id):
        """Override alice's SESSION roles with system_admin (she is base_user
        in DB). Self-assigning a role then succeeds — proving the checks used
        the session-carried roles, not the DB. Roles in a session always
        carry id + code (Session._set_role_codes): ACL reads the ids, the
        field gate reads the codes."""
        from backend.base.crm.security.models.roles import Role

        async with as_user(alice):
            session = get_access_session()
            # As the session build would do (expanded roles, id + code):
            session.user_id.role_ids = [
                Role(id=system_admin_role_id, code="system_admin")
            ]
            await alice.update(
                User(role_ids={"selected": [system_admin_role_id]})
            )

        assert "system_admin" in await _user_role_codes(alice.id)

    async def test_session_without_codes_denies(
        self, alice, system_admin_role_id
    ):
        """A session carrying no codes → restricted write denied (no
        fallback), and crucially does NOT crash on the empty/absent
        role_ids (the `or []` guard)."""
        async with as_user(alice):
            get_access_session().user_id.role_ids = []  # no codes
            with pytest.raises(AccessDenied):
                await alice.update(
                    User(role_ids={"selected": [system_admin_role_id]})
                )


# ============================================================================
# Extra fixtures for scenario / combination tests
# ============================================================================


@pytest_asyncio.fixture
async def second_admin(user_factory):
    """A second superuser — demotion scenarios need more than one admin."""
    return await user_factory(name="Root2", login="root2", is_admin=True)


@pytest_asyncio.fixture
async def inheritor(user_factory, system_admin_role_id):
    """User whose custom role INHERITS system_admin via based_role_ids.

    Validates that role-code expansion (User.get_all_role_codes CTE) grants
    field-level rights through the hierarchy, not only via direct roles.
    """
    from backend.base.crm.security.models.roles import Role

    rid = await Role.create(Role(code="ft_inheritor", name="FT Inheritor"))
    role = await Role.get(rid)
    await role.update(
        Role(based_role_ids={"selected": [system_admin_role_id]})
    )
    return await user_factory(
        name="Inheritor", login="inheritor", role_ids={"selected": [rid]}
    )


# ============================================================================
# Смена роли — role_ids assignment scenarios
# ============================================================================


class TestRoleChangeScenarios:
    async def test_system_admin_removes_role(
        self, sysadmin, target, base_role_id
    ):
        """system_admin may unselect (remove) a user's role."""
        async with as_user(sysadmin):
            await target.update(User(role_ids={"unselected": [base_role_id]}))
        assert "base_user" not in await _user_role_codes(target.id)

    async def test_system_admin_replaces_roles(
        self, sysadmin, target, system_admin_role_id, base_role_id
    ):
        """system_admin may swap a user's role set (select + unselect)."""
        async with as_user(sysadmin):
            await target.update(
                User(
                    role_ids={
                        "selected": [system_admin_role_id],
                        "unselected": [base_role_id],
                    }
                )
            )
        codes = await _user_role_codes(target.id)
        assert "system_admin" in codes and "base_user" not in codes

    async def test_system_admin_adds_role_keeping_existing(
        self, sysadmin, target, system_admin_role_id
    ):
        """Adding a role leaves existing ones → user ends up with several."""
        async with as_user(sysadmin):
            await target.update(
                User(role_ids={"selected": [system_admin_role_id]})
            )
        codes = await _user_role_codes(target.id)
        assert "system_admin" in codes and "base_user" in codes

    async def test_base_user_remove_own_role_denied(self, alice, base_role_id):
        """Any role_ids change by a base user is blocked — incl. removal."""
        async with as_user(alice):
            with pytest.raises(AccessDenied):
                await alice.update(
                    User(role_ids={"unselected": [base_role_id]})
                )
        assert "base_user" in await _user_role_codes(alice.id)

    async def test_inherited_system_admin_can_manage_roles(
        self, inheritor, target, system_admin_role_id
    ):
        """A role inheriting system_admin (based_role_ids) grants the right
        to manage roles — code expansion works through the hierarchy."""
        async with as_user(inheritor):
            await target.update(
                User(role_ids={"selected": [system_admin_role_id]})
            )
        assert "system_admin" in await _user_role_codes(target.id)

    async def test_superuser_removes_roles(
        self, superuser, target, base_role_id
    ):
        """is_admin bypasses the field gate for removals too."""
        async with as_user(superuser):
            await target.update(User(role_ids={"unselected": [base_role_id]}))
        assert "base_user" not in await _user_role_codes(target.id)


# ============================================================================
# Изменение is_admin
# ============================================================================


class TestIsAdminScenarios:
    async def test_system_admin_cannot_promote_via_update(
        self, sysadmin, target
    ):
        """system_admin (not a superuser) cannot flip is_admin on update —
        blocked by the User.update guard (fires before the field check)."""
        async with as_user(sysadmin):
            with pytest.raises(FaraException):
                await target.update(User(is_admin=True))
        refreshed = await User.get(target.id, fields=["id", "is_admin"])
        assert refreshed.is_admin is False

    async def test_base_user_cannot_self_promote(self, alice):
        """A base user cannot make themselves a superuser."""
        async with as_user(alice):
            with pytest.raises(FaraException):
                await alice.update(User(is_admin=True))
        refreshed = await User.get(alice.id, fields=["id", "is_admin"])
        assert refreshed.is_admin is False

    async def test_is_admin_presence_blocks_non_superuser(
        self, sysadmin, target
    ):
        """Presence-based: sending is_admin AT ALL (even its current value)
        is blocked for a non-superuser — the check looks at field PRESENCE,
        not the value or whether it changed. The whole update aborts, so the
        frontend must not send is_admin for users who can't change it."""
        async with as_user(sysadmin):
            with pytest.raises(AccessDenied):
                await target.update(User(name="Renamed", is_admin=False))
        # Atomic: the sibling name change must not have persisted either.
        refreshed = await User.get(target.id, fields=["id", "name"])
        assert refreshed.name == "Target"

    async def test_superuser_demotes_other_admin(
        self, superuser, second_admin
    ):
        """A superuser may demote another admin (not last, not self)."""
        async with as_user(superuser):
            await second_admin.update(User(is_admin=False))
        refreshed = await User.get(second_admin.id, fields=["id", "is_admin"])
        assert refreshed.is_admin is False

    async def test_superuser_cannot_demote_self(self, superuser):
        """Value-rule guard kept atop field-level: cannot revoke own admin."""
        async with as_user(superuser):
            with pytest.raises(FaraException):
                await superuser.update(User(is_admin=False))
        refreshed = await User.get(superuser.id, fields=["id", "is_admin"])
        assert refreshed.is_admin is True

    async def test_superuser_bulk_promote_allowed(self, superuser, target):
        """Superuser may bulk-set is_admin — field gate bypassed."""
        async with as_user(superuser):
            await User.update_bulk([target.id], User(is_admin=True))
        refreshed = await User.get(target.id, fields=["id", "is_admin"])
        assert refreshed.is_admin is True


# ============================================================================
# Комбинации role_ids + is_admin в одном запросе
# ============================================================================


class TestCombinations:
    async def test_denied_field_aborts_whole_update(
        self, alice, system_admin_role_id
    ):
        """A denied field aborts the ENTIRE update atomically — the sibling
        name change in the same payload must not persist either (the field
        check runs before any write)."""
        async with as_user(alice):
            with pytest.raises(AccessDenied):
                await alice.update(
                    User(
                        name="Hacked",
                        role_ids={"selected": [system_admin_role_id]},
                    )
                )
        refreshed = await User.get(alice.id, fields=["id", "name"])
        assert refreshed.name == "Alice"  # unchanged
        assert "system_admin" not in await _user_role_codes(alice.id)

    async def test_superuser_sets_role_and_admin_together(
        self, superuser, target, system_admin_role_id
    ):
        """Superuser sets role_ids + is_admin in one update — both applied."""
        async with as_user(superuser):
            await target.update(
                User(
                    is_admin=True,
                    role_ids={"selected": [system_admin_role_id]},
                )
            )
        refreshed = await User.get(target.id, fields=["id", "is_admin"])
        assert refreshed.is_admin is True
        assert "system_admin" in await _user_role_codes(target.id)

    async def test_system_admin_role_ok_but_admin_blocks(
        self, sysadmin, target, system_admin_role_id
    ):
        """system_admin may set role_ids but not is_admin — the is_admin
        guard aborts the whole payload, so the role is NOT applied either."""
        async with as_user(sysadmin):
            with pytest.raises(FaraException):
                await target.update(
                    User(
                        is_admin=True,
                        role_ids={"selected": [system_admin_role_id]},
                    )
                )
        assert "system_admin" not in await _user_role_codes(target.id)
        refreshed = await User.get(target.id, fields=["id", "is_admin"])
        assert refreshed.is_admin is False
