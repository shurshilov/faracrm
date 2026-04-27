"""
Integration tests for security rules and access control.

Tests the row-level security system:
- @is_member operator (chat membership, project membership)
- @has_parent_access operator (cascade through parent relations)
- @has_polymorphic_parent_access (attachments on different parents)
- Ownership-based rules (leads with user_id)
- Role-based access (different perms per role)

Multiple users with different role combinations are tested to verify
that access rules work correctly in realistic scenarios.

Run: pytest tests/integration/security/test_security_rules.py -v -m integration
"""

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration

from backend.base.system.dotorm.dotorm.access import (
    set_access_session,
    get_access_session,
)
from backend.base.crm.security.models.sessions import Session

# ============================================================================
# Helpers
# ============================================================================


async def _make_session(user) -> Session:
    """
    Build a Session-like object for a user. Doesn't persist to DB —
    just enough for AccessChecker to extract user_id and is_admin.
    """
    return Session(
        id=0,  # dummy
        active=True,
        user_id=user,
        token="test-token",
        ttl=3600,
    )


class as_user:
    """
    Async context manager: temporarily switch access_session to given user.
    Restores previous session on exit (typically SystemSession from conftest).

    Usage:
        async with as_user(alice):
            chats = await Chat.search()
    """

    def __init__(self, user):
        self.user = user
        self._prev = None

    async def __aenter__(self):
        self._prev = get_access_session()
        session = await _make_session(self.user)
        set_access_session(session)
        return session

    async def __aexit__(self, *exc):
        set_access_session(self._prev)


@pytest_asyncio.fixture
async def role_factory(db_pool):
    """Fetches existing role by code (created by app post_init)."""

    async def get_role(code: str):
        from backend.base.crm.security.models.roles import Role

        roles = await Role.search(
            filter=[("code", "=", code)], fields=["id"], limit=1
        )
        return roles[0] if roles else None

    return get_role


@pytest_asyncio.fixture
async def alice(user_factory, role_factory):
    """Internal user with base_user role."""
    base = await role_factory("base_user")
    extra = {}
    if base:
        extra["role_ids"] = {"selected": [base.id]}
    return await user_factory(name="Alice", login="alice", **extra)


@pytest_asyncio.fixture
async def bob(user_factory, role_factory):
    base = await role_factory("base_user")
    extra = {}
    if base:
        extra["role_ids"] = {"selected": [base.id]}
    return await user_factory(name="Bob", login="bob", **extra)


@pytest_asyncio.fixture
async def charlie(user_factory, role_factory):
    base = await role_factory("base_user")
    extra = {}
    if base:
        extra["role_ids"] = {"selected": [base.id]}
    return await user_factory(name="Charlie", login="charlie", **extra)


@pytest_asyncio.fixture
async def crm_user_role(role_factory):
    return await role_factory("crm_user")


@pytest_asyncio.fixture
async def project_user_role(role_factory):
    return await role_factory("project_user")


# ============================================================================
# Chat membership rules (@is_member)
# ============================================================================


class TestChatMembership:
    """
    Rule: chat is visible to its members via @is_member on chat_member.
    Non-members should not see the chat.
    """

    async def test_member_sees_own_chats(self, alice, bob, charlie):
        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_member import ChatMember

        # Alice and Bob in same chat. Charlie not a member.
        chat_id = await Chat.create(Chat(name="Alice-Bob private"))
        await ChatMember.create(
            ChatMember(chat_id=chat_id, user_id=alice.id, is_active=True)
        )
        await ChatMember.create(
            ChatMember(chat_id=chat_id, user_id=bob.id, is_active=True)
        )

        # Alice sees the chat
        async with as_user(alice):
            chats = await Chat.search(filter=[("id", "=", chat_id)])
            assert len(chats) == 1
            assert chats[0].id == chat_id

        # Bob sees the chat
        async with as_user(bob):
            chats = await Chat.search(filter=[("id", "=", chat_id)])
            assert len(chats) == 1

        # Charlie does NOT see the chat
        async with as_user(charlie):
            chats = await Chat.search(filter=[("id", "=", chat_id)])
            assert len(chats) == 0

    async def test_inactive_member_loses_access(self, alice, bob):
        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_member import ChatMember

        chat_id = await Chat.create(Chat(name="Test chat"))
        await ChatMember.create(
            ChatMember(chat_id=chat_id, user_id=alice.id, is_active=True)
        )
        membership = await ChatMember.create(
            ChatMember(chat_id=chat_id, user_id=bob.id, is_active=True)
        )

        # Bob sees the chat while active
        async with as_user(bob):
            chats = await Chat.search(filter=[("id", "=", chat_id)])
            assert len(chats) == 1

        # Mark Bob as inactive
        bob_member = await ChatMember.get(membership)
        bob_member.is_active = False
        await bob_member.update(payload=bob_member)

        # Bob no longer sees the chat
        async with as_user(bob):
            chats = await Chat.search(filter=[("id", "=", chat_id)])
            assert len(chats) == 0

    async def test_admin_sees_all_chats(self, user_factory):
        from backend.base.crm.chat.models.chat import Chat

        admin = await user_factory(
            name="SystemAdmin", login="sysadmin", is_admin=True
        )
        c1 = await Chat.create(Chat(name="Chat A"))
        c2 = await Chat.create(Chat(name="Chat B"))
        # No memberships at all
        async with as_user(admin):
            chats = await Chat.search(
                filter=[("id", "in", [c1, c2])], fields=["id", "name"]
            )
            assert len(chats) == 2


# ============================================================================
# Chat messages — @is_member on chat_message
# ============================================================================


class TestChatMessages:
    async def test_member_sees_messages(self, alice, bob, charlie):
        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_member import ChatMember
        from backend.base.crm.chat.models.chat_message import ChatMessage

        chat_id = await Chat.create(Chat(name="Talk"))
        await ChatMember.create(
            ChatMember(chat_id=chat_id, user_id=alice.id, is_active=True)
        )
        await ChatMember.create(
            ChatMember(chat_id=chat_id, user_id=bob.id, is_active=True)
        )

        await ChatMessage.create(
            ChatMessage(chat_id=chat_id, body="hello", author_user_id=alice.id)
        )
        await ChatMessage.create(
            ChatMessage(chat_id=chat_id, body="hi back", author_user_id=bob.id)
        )

        async with as_user(alice):
            msgs = await ChatMessage.search(
                filter=[("chat_id", "=", chat_id)], fields=["id", "body"]
            )
            assert len(msgs) == 2

        async with as_user(charlie):
            msgs = await ChatMessage.search(
                filter=[("chat_id", "=", chat_id)], fields=["id", "body"]
            )
            assert len(msgs) == 0

    async def test_messages_isolated_between_chats(self, alice, bob):
        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_member import ChatMember
        from backend.base.crm.chat.models.chat_message import ChatMessage

        # Two chats: alice in chat A, bob in chat B (separate)
        chat_a = await Chat.create(Chat(name="A"))
        chat_b = await Chat.create(Chat(name="B"))
        await ChatMember.create(
            ChatMember(chat_id=chat_a, user_id=alice.id, is_active=True)
        )
        await ChatMember.create(
            ChatMember(chat_id=chat_b, user_id=bob.id, is_active=True)
        )

        await ChatMessage.create(ChatMessage(chat_id=chat_a, body="A1"))
        await ChatMessage.create(ChatMessage(chat_id=chat_a, body="A2"))
        await ChatMessage.create(ChatMessage(chat_id=chat_b, body="B1"))

        async with as_user(alice):
            msgs = await ChatMessage.search(fields=["id", "body", "chat_id"])
            bodies = {m.body for m in msgs}
            assert bodies == {"A1", "A2"}

        async with as_user(bob):
            msgs = await ChatMessage.search(fields=["id", "body", "chat_id"])
            bodies = {m.body for m in msgs}
            assert bodies == {"B1"}


# ============================================================================
# Polymorphic attachments — @has_polymorphic_parent_access
# ============================================================================


class TestAttachmentsOnPartners:
    """
    Partners have no row-level rules → all base_users see all partners.
    Therefore attachments on partners are visible to everyone with read
    access to the parent (which is everyone authenticated).
    """

    async def test_partner_attachments_visible_to_all(
        self, alice, bob, partner_factory
    ):
        from backend.base.crm.attachments.models.attachments import Attachment

        p = await partner_factory(name="Acme Inc")
        a1 = await Attachment.create(
            Attachment(
                name="contract.pdf",
                mimetype="application/pdf",
                size=100,
                res_model="partners",
                res_id=p.id,
            )
        )

        async with as_user(alice):
            atts = await Attachment.search(
                filter=[("res_model", "=", "partners")],
                fields=["id", "name", "res_id"],
            )
            assert any(a.id == a1 for a in atts)

        async with as_user(bob):
            atts = await Attachment.search(
                filter=[("res_model", "=", "partners")],
                fields=["id", "name", "res_id"],
            )
            assert any(a.id == a1 for a in atts)

    async def test_orphan_partner_attachment_hidden(self, alice):
        """
        If parent partner doesn't exist, attachment is hidden — by design,
        the polymorphic operator filters by SELECT id FROM partners.
        """
        from backend.base.crm.attachments.models.attachments import Attachment

        # res_id = 999999 is non-existent
        a_orphan = await Attachment.create(
            Attachment(
                name="orphan.txt",
                mimetype="text/plain",
                size=10,
                res_model="partners",
                res_id=999999,
            )
        )

        async with as_user(alice):
            atts = await Attachment.search(
                filter=[("res_model", "=", "partners")],
                fields=["id", "res_id"],
            )
            assert not any(a.id == a_orphan for a in atts)


class TestAttachmentsOnChats:
    """
    Attachments on chat_message are visible only to chat members.
    @has_polymorphic_parent_access cascades through chat_message rules
    which use @is_member.
    """

    async def test_chat_attachment_visible_to_member(
        self, alice, bob, charlie
    ):
        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_member import ChatMember
        from backend.base.crm.chat.models.chat_message import ChatMessage
        from backend.base.crm.attachments.models.attachments import Attachment

        chat_id = await Chat.create(Chat(name="Files chat"))
        await ChatMember.create(
            ChatMember(chat_id=chat_id, user_id=alice.id, is_active=True)
        )
        await ChatMember.create(
            ChatMember(chat_id=chat_id, user_id=bob.id, is_active=True)
        )
        msg_id = await ChatMessage.create(
            ChatMessage(
                chat_id=chat_id,
                body="here is a file",
                author_user_id=alice.id,
            )
        )

        att_id = await Attachment.create(
            Attachment(
                name="report.pdf",
                mimetype="application/pdf",
                size=200,
                res_model="chat_message",
                res_id=msg_id,
            )
        )

        # Alice (member) sees the attachment
        async with as_user(alice):
            atts = await Attachment.search(
                filter=[("res_model", "=", "chat_message")],
                fields=["id", "res_id"],
            )
            assert any(a.id == att_id for a in atts)

        # Charlie (non-member) does not
        async with as_user(charlie):
            atts = await Attachment.search(
                filter=[("res_model", "=", "chat_message")],
                fields=["id", "res_id"],
            )
            assert not any(a.id == att_id for a in atts)

    async def test_public_attachment_visible_to_all(self, alice, charlie):
        """Public attachment is visible regardless of parent access."""
        from backend.base.crm.attachments.models.attachments import Attachment

        att_id = await Attachment.create(
            Attachment(
                name="public.pdf",
                mimetype="application/pdf",
                size=50,
                public=True,
                res_model="chat_message",
                res_id=999999,  # parent doesn't exist
            )
        )

        async with as_user(alice):
            atts = await Attachment.search(
                filter=[("id", "=", att_id)], fields=["id"]
            )
            assert len(atts) == 1

        async with as_user(charlie):
            atts = await Attachment.search(
                filter=[("id", "=", att_id)], fields=["id"]
            )
            assert len(atts) == 1


class TestAttachmentsOnLeads:
    """
    Lead has ownership-based rules:
      crm_user role: lead.user_id = me OR lead.user_id IS NULL
    Other crm_user's lead is invisible → attachments on it also invisible.
    """

    async def test_lead_attachment_visible_to_owner(
        self, user_factory, role_factory, lead_factory
    ):
        from backend.base.crm.attachments.models.attachments import Attachment

        crm_user = await role_factory("crm_user")
        if crm_user is None:
            pytest.skip("crm_user role missing — leads app not initialized")

        u1 = await user_factory(
            name="Alice CRM",
            login="alice_crm",
            role_ids={"selected": [crm_user.id]},
        )
        u2 = await user_factory(
            name="Dave CRM",
            login="dave_crm",
            role_ids={"selected": [crm_user.id]},
        )

        # Lead owned by u1
        lead = await lead_factory(name="Hot Prospect", user_id=u1.id)

        att = await Attachment.create(
            Attachment(
                name="proposal.pdf",
                mimetype="application/pdf",
                size=300,
                res_model="leads",
                res_id=lead.id,
            )
        )

        # Owner (u1) sees the attachment
        async with as_user(u1):
            atts = await Attachment.search(
                filter=[("res_model", "=", "leads")],
                fields=["id", "res_id"],
            )
            assert any(a.id == att for a in atts)

        # Other crm_user (u2) does NOT see u1's lead → no attachment
        async with as_user(u2):
            atts = await Attachment.search(
                filter=[("res_model", "=", "leads")],
                fields=["id", "res_id"],
            )
            assert not any(a.id == att for a in atts)

    async def test_unassigned_lead_attachment_visible_to_crm_users(
        self, user_factory, role_factory, lead_factory
    ):
        """user_id IS NULL → visible to all crm_user."""
        from backend.base.crm.attachments.models.attachments import Attachment

        crm_user = await role_factory("crm_user")
        if crm_user is None:
            pytest.skip("crm_user role missing")

        u1 = await user_factory(
            name="U1", login="u1", role_ids={"selected": [crm_user.id]}
        )
        u2 = await user_factory(
            name="U2", login="u2", role_ids={"selected": [crm_user.id]}
        )

        lead = await lead_factory(name="Unassigned", user_id=None)
        att = await Attachment.create(
            Attachment(
                name="generic.pdf",
                mimetype="application/pdf",
                size=80,
                res_model="leads",
                res_id=lead.id,
            )
        )

        for u in (u1, u2):
            async with as_user(u):
                atts = await Attachment.search(
                    filter=[("id", "=", att)], fields=["id"]
                )
                assert len(atts) == 1, f"User {u.login} should see attachment"


# ============================================================================
# Project membership rules
# ============================================================================


class TestProjectMembership:
    """
    Project rules (project_user role):
      manager_id = me  OR  member_ids contains me
    """

    async def test_manager_sees_own_project(self, user_factory, role_factory):
        from backend.base.crm.tasks.models.project import Project

        project_user = await role_factory("project_user")
        if project_user is None:
            pytest.skip("project_user role missing")

        u_mgr = await user_factory(
            name="Mgr", login="mgr", role_ids={"selected": [project_user.id]}
        )
        u_other = await user_factory(
            name="Other",
            login="other",
            role_ids={"selected": [project_user.id]},
        )

        # Project managed by u_mgr
        async with as_user(u_mgr):
            # We want manager_id to be u_mgr — we're the session, default
            # _default_current_user picks current user
            pid = await Project.create(Project(name="MyProj"))

        async with as_user(u_mgr):
            projects = await Project.search(
                filter=[("id", "=", pid)], fields=["id", "name"]
            )
            assert len(projects) == 1

        async with as_user(u_other):
            projects = await Project.search(
                filter=[("id", "=", pid)], fields=["id", "name"]
            )
            assert len(projects) == 0

    async def test_project_member_sees_project(
        self, user_factory, role_factory
    ):
        from backend.base.crm.tasks.models.project import Project
        from backend.base.crm.tasks.models.project_member import ProjectMember

        project_user = await role_factory("project_user")
        if project_user is None:
            pytest.skip("project_user role missing")

        u_mgr = await user_factory(
            name="Manager",
            login="pm",
            role_ids={"selected": [project_user.id]},
        )
        u_member = await user_factory(
            name="Member",
            login="member",
            role_ids={"selected": [project_user.id]},
        )
        u_outsider = await user_factory(
            name="Outsider",
            login="outsider",
            role_ids={"selected": [project_user.id]},
        )

        async with as_user(u_mgr):
            pid = await Project.create(Project(name="Joint Project"))

        # Add u_member as member
        await ProjectMember.create(
            ProjectMember(project_id=pid, user_id=u_member.id, is_active=True)
        )

        # Member sees
        async with as_user(u_member):
            projects = await Project.search(
                filter=[("id", "=", pid)], fields=["id"]
            )
            assert len(projects) == 1

        # Outsider does not
        async with as_user(u_outsider):
            projects = await Project.search(
                filter=[("id", "=", pid)], fields=["id"]
            )
            assert len(projects) == 0


# ============================================================================
# Tasks within projects
# ============================================================================


class TestTaskAccess:
    """
    Task visibility cascades from project membership:
      project_id.manager_id = me OR project_id.member_ids contains me
    """

    async def test_task_visible_only_via_project(
        self, user_factory, role_factory
    ):
        from backend.base.crm.tasks.models.project import Project
        from backend.base.crm.tasks.models.task import Task

        project_user = await role_factory("project_user")
        if project_user is None:
            pytest.skip("project_user role missing")

        u_mgr = await user_factory(
            name="PM", login="pmgr", role_ids={"selected": [project_user.id]}
        )
        u_other = await user_factory(
            name="Other2",
            login="other2",
            role_ids={"selected": [project_user.id]},
        )

        async with as_user(u_mgr):
            pid = await Project.create(Project(name="Task Project"))
            tid = await Task.create(
                Task(name="Implement feature", project_id=pid)
            )

        # Manager sees their task
        async with as_user(u_mgr):
            tasks = await Task.search(
                filter=[("id", "=", tid)], fields=["id", "name"]
            )
            assert len(tasks) == 1

        # Outsider does not
        async with as_user(u_other):
            tasks = await Task.search(
                filter=[("id", "=", tid)], fields=["id", "name"]
            )
            assert len(tasks) == 0

    async def test_attachments_on_task_via_project(
        self, user_factory, role_factory
    ):
        """Attachments on task should follow task's visibility rules."""
        from backend.base.crm.tasks.models.project import Project
        from backend.base.crm.tasks.models.task import Task
        from backend.base.crm.attachments.models.attachments import Attachment

        project_user = await role_factory("project_user")
        if project_user is None:
            pytest.skip("project_user role missing")

        u_mgr = await user_factory(
            name="TaskPM",
            login="taskpm",
            role_ids={"selected": [project_user.id]},
        )
        u_outsider = await user_factory(
            name="O", login="o3", role_ids={"selected": [project_user.id]}
        )

        async with as_user(u_mgr):
            pid = await Project.create(Project(name="P"))
            tid = await Task.create(Task(name="T", project_id=pid))

        att_id = await Attachment.create(
            Attachment(
                name="task_doc.pdf",
                mimetype="application/pdf",
                size=120,
                res_model="task",
                res_id=tid,
            )
        )

        # Manager sees attachment via task → project visibility
        async with as_user(u_mgr):
            atts = await Attachment.search(
                filter=[("id", "=", att_id)], fields=["id"]
            )
            assert len(atts) == 1

        # Outsider doesn't see task → doesn't see attachment
        async with as_user(u_outsider):
            atts = await Attachment.search(
                filter=[("id", "=", att_id)], fields=["id"]
            )
            assert len(atts) == 0


# ============================================================================
# Multi-role combinations
# ============================================================================


class TestRoleCombinations:
    async def test_user_with_both_roles(
        self, user_factory, role_factory, lead_factory
    ):
        """User with crm_user + crm_manager sees all leads (manager wins)."""
        from backend.base.crm.leads.models.leads import Lead

        crm_user = await role_factory("crm_user")
        crm_manager = await role_factory("crm_manager")
        if crm_user is None or crm_manager is None:
            pytest.skip("crm roles missing")

        u_owner = await user_factory(
            name="Owner",
            login="owner",
            role_ids={"selected": [crm_user.id]},
        )
        u_dual = await user_factory(
            name="Dual",
            login="dual",
            role_ids={"selected": [crm_user.id, crm_manager.id]},
        )

        # Lead owned by u_owner
        lead_a = await lead_factory(name="Lead A", user_id=u_owner.id)
        lead_b = await lead_factory(name="Lead B", user_id=u_dual.id)

        # u_dual has crm_manager → sees ALL leads, even u_owner's
        async with as_user(u_dual):
            leads = await Lead.search(
                filter=[("id", "in", [lead_a.id, lead_b.id])],
                fields=["id", "name"],
            )
            assert len(leads) == 2

        # u_owner only crm_user → sees only their own
        async with as_user(u_owner):
            leads = await Lead.search(
                filter=[("id", "in", [lead_a.id, lead_b.id])],
                fields=["id", "name"],
            )
            assert len(leads) == 1
            assert leads[0].id == lead_a.id

    async def test_admin_bypasses_all_rules(self, user_factory, lead_factory):
        from backend.base.crm.leads.models.leads import Lead
        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.attachments.models.attachments import Attachment

        admin = await user_factory(name="GodMode", login="god", is_admin=True)
        # Random data not owned by admin
        await lead_factory(name="Some lead", user_id=None)
        await Chat.create(Chat(name="Random chat"))
        await Attachment.create(
            Attachment(
                name="orphan.txt",
                mimetype="text/plain",
                size=1,
                res_model="partners",
                res_id=99999,
            )
        )

        async with as_user(admin):
            # admin sees everything ignoring rules
            assert len(await Lead.search()) >= 1
            assert len(await Chat.search()) >= 1
            assert len(await Attachment.search()) >= 1
