"""
Integration tests for SavedFilter module.

Tests cover:
- SavedFilter CRUD
- Per-user filters vs global filters
- Default filter logic
- Filter by model_name
- Use count tracking

Run: pytest tests/integration/saved_filters/test_saved_filters.py -v -m integration
"""

import pytest
import json

pytestmark = pytest.mark.integration


class TestSavedFilterCRUD:
    """Tests for SavedFilter model basic CRUD."""

    async def test_create_saved_filter(self):
        from backend.base.system.saved_filters.models.saved_filter import SavedFilter

        filter_data = json.dumps([["name", "ilike", "%test%"]])
        sf_id = await SavedFilter.create(
            SavedFilter(
                name="Test Filter",
                model_name="partners",
                filter_data=filter_data,
            )
        )
        sf = await SavedFilter.get(sf_id)
        assert sf.name == "Test Filter"
        assert sf.model_name == "partners"
        assert json.loads(sf.filter_data) == [["name", "ilike", "%test%"]]

    async def test_create_filter_with_user(self, user_factory):
        from backend.base.system.saved_filters.models.saved_filter import SavedFilter

        user = await user_factory(name="Filter Owner", login="filter_owner")

        sf_id = await SavedFilter.create(
            SavedFilter(
                name="My Filter",
                model_name="leads",
                filter_data='[["stage_id", "=", 1]]',
                user_id=user.id,
            )
        )
        sf = await SavedFilter.get(sf_id)
        assert sf.name == "My Filter"

    async def test_search_filters_by_model(self):
        from backend.base.system.saved_filters.models.saved_filter import SavedFilter

        await SavedFilter.create(
            SavedFilter(name="F1", model_name="partners", filter_data="[]")
        )
        await SavedFilter.create(
            SavedFilter(name="F2", model_name="partners", filter_data="[]")
        )
        await SavedFilter.create(
            SavedFilter(name="F3", model_name="leads", filter_data="[]")
        )

        partner_filters = await SavedFilter.search(
            fields=["id", "name"],
            filter=[("model_name", "=", "partners")],
        )
        assert len(partner_filters) == 2

    async def test_update_filter(self):
        from backend.base.system.saved_filters.models.saved_filter import SavedFilter

        sf_id = await SavedFilter.create(
            SavedFilter(name="Old Name", model_name="users", filter_data="[]")
        )
        sf = await SavedFilter.get(sf_id)

        new_filter = json.dumps([["is_admin", "=", True]])
        await sf.update(SavedFilter(name="Admin Filter", filter_data=new_filter))

        updated = await SavedFilter.get(sf_id)
        assert updated.name == "Admin Filter"
        assert json.loads(updated.filter_data) == [["is_admin", "=", True]]

    async def test_delete_filter(self):
        from backend.base.system.saved_filters.models.saved_filter import SavedFilter

        sf_id = await SavedFilter.create(
            SavedFilter(name="Delete Me", model_name="users", filter_data="[]")
        )
        sf = await SavedFilter.get(sf_id)
        await sf.delete()
        assert await SavedFilter.get_or_none(sf_id) is None


class TestSavedFilterGlobal:
    """Tests for global vs personal filters."""

    async def test_global_filter(self):
        from backend.base.system.saved_filters.models.saved_filter import SavedFilter

        sf_id = await SavedFilter.create(
            SavedFilter(
                name="Global Filter",
                model_name="partners",
                filter_data="[]",
                is_global=True,
            )
        )
        sf = await SavedFilter.get(sf_id)
        assert sf.is_global is True

    async def test_search_global_filters(self, user_factory):
        from backend.base.system.saved_filters.models.saved_filter import SavedFilter

        user = await user_factory(name="U", login="u_global")

        # Global filter
        await SavedFilter.create(
            SavedFilter(
                name="Shared",
                model_name="leads",
                filter_data="[]",
                is_global=True,
            )
        )
        # Personal filter
        await SavedFilter.create(
            SavedFilter(
                name="Personal",
                model_name="leads",
                filter_data="[]",
                user_id=user.id,
                is_global=False,
            )
        )

        global_filters = await SavedFilter.search(
            fields=["id", "name"],
            filter=[("model_name", "=", "leads"), ("is_global", "=", True)],
        )
        assert len(global_filters) == 1
        assert global_filters[0].name == "Shared"


class TestSavedFilterDefault:
    """Tests for default filter functionality."""

    async def test_default_filter(self):
        from backend.base.system.saved_filters.models.saved_filter import SavedFilter

        sf_id = await SavedFilter.create(
            SavedFilter(
                name="Default Partners View",
                model_name="partners",
                filter_data='[["is_customer", "=", true]]',
                is_default=True,
            )
        )
        sf = await SavedFilter.get(sf_id)
        assert sf.is_default is True

    async def test_search_default_for_model(self):
        from backend.base.system.saved_filters.models.saved_filter import SavedFilter

        await SavedFilter.create(
            SavedFilter(
                name="Default", model_name="partners",
                filter_data="[]", is_default=True,
            )
        )
        await SavedFilter.create(
            SavedFilter(
                name="Not Default", model_name="partners",
                filter_data="[]", is_default=False,
            )
        )

        defaults = await SavedFilter.search(
            fields=["id", "name"],
            filter=[
                ("model_name", "=", "partners"),
                ("is_default", "=", True),
            ],
        )
        assert len(defaults) == 1
        assert defaults[0].name == "Default"


class TestSavedFilterUsage:
    """Tests for usage tracking."""

    async def test_initial_use_count(self):
        from backend.base.system.saved_filters.models.saved_filter import SavedFilter

        sf_id = await SavedFilter.create(
            SavedFilter(name="New", model_name="leads", filter_data="[]")
        )
        sf = await SavedFilter.get(sf_id)
        assert sf.use_count == 0

    async def test_increment_use_count(self):
        from backend.base.system.saved_filters.models.saved_filter import SavedFilter
        from datetime import datetime, timezone

        sf_id = await SavedFilter.create(
            SavedFilter(name="Popular", model_name="leads", filter_data="[]")
        )
        sf = await SavedFilter.get(sf_id)

        await sf.update(SavedFilter(
            use_count=sf.use_count + 1,
            last_used_at=datetime.now(timezone.utc),
        ))

        updated = await SavedFilter.get(sf_id)
        assert updated.use_count == 1
        assert updated.last_used_at is not None

    async def test_complex_filter_data(self):
        """Ensure complex JSON filter data round-trips correctly."""
        from backend.base.system.saved_filters.models.saved_filter import SavedFilter

        complex_filter = json.dumps([
            ["stage_id", "=", 2],
            "and",
            [
                ["expected_revenue", ">", 10000],
                "or",
                ["priority", "=", "high"],
            ],
        ])

        sf_id = await SavedFilter.create(
            SavedFilter(
                name="Complex",
                model_name="leads",
                filter_data=complex_filter,
            )
        )
        sf = await SavedFilter.get(sf_id)
        parsed = json.loads(sf.filter_data)
        assert len(parsed) == 3
        assert parsed[1] == "and"
