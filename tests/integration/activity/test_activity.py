"""
Integration tests for Activity module.

Tests cover:
- ActivityType CRUD
- Activity CRUD
- Polymorphic binding (res_model/res_id)
- State transitions (planned → today → overdue → done → cancelled)
- Search by user, model, state, deadline

Run: pytest tests/integration/activity/test_activity.py -v -m integration
"""

import pytest
from datetime import date, timedelta, datetime, timezone

pytestmark = pytest.mark.integration


# ====================
# ActivityType Tests
# ====================


class TestActivityType:
    """Tests for ActivityType model."""

    async def test_create_activity_type(self):
        from backend.base.crm.activity.models.activity_type import ActivityType

        at_id = await ActivityType.create(
            ActivityType(
                name="Звонок",
                icon="IconPhone",
                color="#22b8cf",
                default_days=0,
                sequence=1,
            )
        )
        at = await ActivityType.get(at_id)
        assert at.name == "Звонок"
        assert at.default_days == 0

    async def test_create_all_initial_types(self):
        from backend.base.crm.activity.models.activity_type import (
            ActivityType,
            INITIAL_ACTIVITY_TYPES,
        )

        for data in INITIAL_ACTIVITY_TYPES:
            await ActivityType.create(ActivityType(**data))

        all_types = await ActivityType.search(fields=["id", "name"])
        assert len(all_types) == len(INITIAL_ACTIVITY_TYPES)

    async def test_search_active_types(self):
        from backend.base.crm.activity.models.activity_type import ActivityType

        await ActivityType.create(
            ActivityType(name="Active", active=True, sequence=1)
        )
        await ActivityType.create(
            ActivityType(name="Inactive", active=False, sequence=2)
        )

        active = await ActivityType.search(
            fields=["id", "name"],
            filter=[("active", "=", True)],
        )
        names = [t.name for t in active]
        assert "Active" in names
        assert "Inactive" not in names

    async def test_update_activity_type(self):
        from backend.base.crm.activity.models.activity_type import ActivityType

        at_id = await ActivityType.create(
            ActivityType(name="Old Name", default_days=1, sequence=1)
        )
        at = await ActivityType.get(at_id)
        await at.update(ActivityType(name="New Name", default_days=5))

        updated = await ActivityType.get(at_id)
        assert updated.name == "New Name"
        assert updated.default_days == 5

    async def test_delete_activity_type(self):
        from backend.base.crm.activity.models.activity_type import ActivityType

        at_id = await ActivityType.create(
            ActivityType(name="To Delete", sequence=1)
        )
        at = await ActivityType.get(at_id)
        await at.delete()
        assert await ActivityType.get_or_none(at_id) is None


# ====================
# Activity CRUD Tests
# ====================


class TestActivityCRUD:
    """Tests for Activity model basic CRUD."""

    async def _create_deps(self):
        from backend.base.crm.activity.models.activity_type import ActivityType
        from backend.base.crm.users.models.users import User
        from backend.base.crm.languages.models.language import Language

        at_id = await ActivityType.create(
            ActivityType(name="Test Type", default_days=1, sequence=1)
        )
        lang_id = await Language.create(
            Language(code="en", name="English", active=True)
        )
        user_id = await User.create(
            User(
                name="Test User",
                login="activity_user",
                password_hash="h",
                password_salt="s",
                lang_id=lang_id,
            )
        )
        return at_id, user_id

    async def test_create_activity(self):
        from backend.base.crm.activity.models.activity import Activity

        at_id, user_id = await self._create_deps()

        aid = await Activity.create(
            Activity(
                res_model="lead",
                res_id=1,
                activity_type_id=at_id,
                summary="Позвонить клиенту",
                date_deadline=date.today() + timedelta(days=3),
                user_id=user_id,
                state="planned",
            )
        )
        a = await Activity.get(aid)
        assert a.res_model == "lead"
        assert a.summary == "Позвонить клиенту"
        assert a.state == "planned"
        assert a.done is False

    async def test_polymorphic_binding(self):
        """Activities can bind to any model via res_model/res_id."""
        from backend.base.crm.activity.models.activity import Activity

        at_id, user_id = await self._create_deps()
        dl = date.today() + timedelta(days=1)

        await Activity.create(
            Activity(
                res_model="lead", res_id=10,
                activity_type_id=at_id, date_deadline=dl, user_id=user_id,
            )
        )
        await Activity.create(
            Activity(
                res_model="task", res_id=20,
                activity_type_id=at_id, date_deadline=dl, user_id=user_id,
            )
        )
        await Activity.create(
            Activity(
                res_model="partner", res_id=30,
                activity_type_id=at_id, date_deadline=dl, user_id=user_id,
            )
        )

        lead_acts = await Activity.search(
            fields=["id"], filter=[("res_model", "=", "lead")]
        )
        assert len(lead_acts) == 1

        task_acts = await Activity.search(
            fields=["id"], filter=[("res_model", "=", "task")]
        )
        assert len(task_acts) == 1

    async def test_search_by_user(self):
        from backend.base.crm.activity.models.activity import Activity
        from backend.base.crm.users.models.users import User
        from backend.base.crm.languages.models.language import Language
        from backend.base.crm.activity.models.activity_type import ActivityType

        at_id = await ActivityType.create(
            ActivityType(name="T", default_days=1, sequence=1)
        )
        lang_id = await Language.create(
            Language(code="en", name="English", active=True)
        )
        u1 = await User.create(
            User(name="A", login="a", password_hash="h", password_salt="s", lang_id=lang_id)
        )
        u2 = await User.create(
            User(name="B", login="b", password_hash="h", password_salt="s", lang_id=lang_id)
        )
        dl = date.today() + timedelta(days=1)

        for i in range(3):
            await Activity.create(
                Activity(res_model="lead", res_id=i, activity_type_id=at_id,
                         date_deadline=dl, user_id=u1)
            )
        await Activity.create(
            Activity(res_model="lead", res_id=99, activity_type_id=at_id,
                     date_deadline=dl, user_id=u2)
        )

        u1_acts = await Activity.search(fields=["id"], filter=[("user_id", "=", u1)])
        assert len(u1_acts) == 3

    async def test_state_transition_to_done(self):
        from backend.base.crm.activity.models.activity import Activity

        at_id, user_id = await self._create_deps()

        aid = await Activity.create(
            Activity(
                res_model="partner", res_id=5, activity_type_id=at_id,
                date_deadline=date.today(), user_id=user_id, state="planned",
            )
        )
        a = await Activity.get(aid)
        now = datetime.now(timezone.utc)
        await a.update(Activity(state="done", done=True, done_datetime=now))

        updated = await Activity.get(aid)
        assert updated.state == "done"
        assert updated.done is True
        assert updated.done_datetime is not None

    async def test_state_cancelled(self):
        from backend.base.crm.activity.models.activity import Activity

        at_id, user_id = await self._create_deps()

        aid = await Activity.create(
            Activity(
                res_model="lead", res_id=1, activity_type_id=at_id,
                date_deadline=date.today(), user_id=user_id, state="planned",
            )
        )
        a = await Activity.get(aid)
        await a.update(Activity(state="cancelled"))

        updated = await Activity.get(aid)
        assert updated.state == "cancelled"

    async def test_search_overdue(self):
        from backend.base.crm.activity.models.activity import Activity

        at_id, user_id = await self._create_deps()

        # Overdue
        await Activity.create(
            Activity(
                res_model="lead", res_id=1, activity_type_id=at_id,
                date_deadline=date.today() - timedelta(days=5),
                user_id=user_id, state="overdue", done=False,
            )
        )
        # Future (not overdue)
        await Activity.create(
            Activity(
                res_model="lead", res_id=2, activity_type_id=at_id,
                date_deadline=date.today() + timedelta(days=5),
                user_id=user_id, state="planned", done=False,
            )
        )
        # Done (not overdue)
        await Activity.create(
            Activity(
                res_model="lead", res_id=3, activity_type_id=at_id,
                date_deadline=date.today() - timedelta(days=1),
                user_id=user_id, state="done", done=True,
            )
        )

        overdue = await Activity.search(
            fields=["id"],
            filter=[("state", "=", "overdue"), ("done", "=", False)],
        )
        assert len(overdue) == 1

    async def test_delete_activity(self):
        from backend.base.crm.activity.models.activity import Activity

        at_id, user_id = await self._create_deps()

        aid = await Activity.create(
            Activity(
                res_model="lead", res_id=1, activity_type_id=at_id,
                date_deadline=date.today(), user_id=user_id,
            )
        )
        a = await Activity.get(aid)
        await a.delete()
        assert await Activity.get_or_none(aid) is None

    async def test_notification_sent_flag(self):
        from backend.base.crm.activity.models.activity import Activity

        at_id, user_id = await self._create_deps()

        aid = await Activity.create(
            Activity(
                res_model="lead", res_id=1, activity_type_id=at_id,
                date_deadline=date.today(), user_id=user_id,
                notification_sent=False,
            )
        )

        # Simulate notification sent
        a = await Activity.get(aid)
        await a.update(Activity(notification_sent=True))

        updated = await Activity.get(aid)
        assert updated.notification_sent is True

    async def test_search_pending_notifications(self):
        """Find activities that need notifications (today/overdue, not sent)."""
        from backend.base.crm.activity.models.activity import Activity

        at_id, user_id = await self._create_deps()

        # Needs notification
        await Activity.create(
            Activity(
                res_model="lead", res_id=1, activity_type_id=at_id,
                date_deadline=date.today(), user_id=user_id,
                state="today", done=False, notification_sent=False,
            )
        )
        # Already notified
        await Activity.create(
            Activity(
                res_model="lead", res_id=2, activity_type_id=at_id,
                date_deadline=date.today(), user_id=user_id,
                state="today", done=False, notification_sent=True,
            )
        )

        pending = await Activity.search(
            fields=["id"],
            filter=[
                ("done", "=", False),
                ("notification_sent", "=", False),
                ("state", "!=", "cancelled"),
            ],
        )
        assert len(pending) == 1
