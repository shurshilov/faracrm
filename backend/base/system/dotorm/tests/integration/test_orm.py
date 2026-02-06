"""
Integration tests for DotORM.

Requires PostgreSQL database 'dotorm_test' running locally.
Run with: pytest tests/integration/ -v -m integration

DO NOT RUN AUTOMATICALLY - requires database setup.
"""

import pytest
from datetime import datetime, date, time
from decimal import Decimal


# ====================
# Mark all tests as integration
# ====================

pytestmark = pytest.mark.integration


# ====================
# Basic CRUD Tests
# ====================


class TestCreate:
    """Tests for create operations."""

    async def test_create_simple_model(self, session, clean_tables):
        """Test creating a simple model."""
        from .models import Model

        model_id = await Model.create(Model(name="test_model"))

        assert model_id is not None
        assert isinstance(model_id, int)
        assert model_id > 0

    async def test_create_with_all_fields(self, session, clean_tables):
        """Test creating model with all fields."""
        from .models import User

        user = User(
            name="Test User",
            login="testuser",
            email="test@example.com",
            password_hash="hash123",
            password_salt="salt123",
        )
        user_id = await User.create(user)

        assert user_id > 0

        # Verify created record
        created_user = await User.get(user_id)
        assert created_user is not None
        assert created_user.name == "Test User"
        assert created_user.login == "testuser"
        assert created_user.email == "test@example.com"

    async def test_create_with_nullable_fields(self, session, clean_tables):
        """Test creating model with NULL fields."""
        from .models import User

        user = User(
            name="User Without Login",
            email="nologin@example.com",
            password_hash="hash",
            password_salt="salt",
            # login is None
        )
        user_id = await User.create(user)

        created = await User.get(user_id)
        assert created.login is None

    async def test_create_with_default_values(self, session, clean_tables):
        """Test creating model with default values."""
        from .models import DefaultValuesModel

        record = DefaultValuesModel(name="Test")
        record_id = await DefaultValuesModel.create(record)

        created = await DefaultValuesModel.get(record_id)
        assert created.status == "draft"
        assert created.active is True
        assert created.counter == 0
        assert created.priority == 10

    async def test_create_bulk(self, session, clean_tables):
        """Test bulk create."""
        from .models import Model

        models = [
            Model(name="model_1"),
            Model(name="model_2"),
            Model(name="model_3"),
        ]
        result = await Model.create_bulk(models)

        assert len(result) == 3
        for record in result:
            assert "id" in record
            assert record["id"] > 0


class TestGet:
    """Tests for get (read) operations."""

    async def test_get_by_id(self, sample_data):
        """Test getting record by ID."""
        from .models import User

        user_id = sample_data["users"][0]
        user = await User.get(user_id)

        assert user is not None
        assert user.id == user_id
        assert user.name == "John Doe"

    async def test_get_nonexistent_returns_none(self, session, clean_tables):
        """Test getting non-existent record returns None."""
        from .models import User

        user = await User.get(99999)
        assert user is None

    async def test_get_with_specific_fields(self, sample_data):
        """Test getting record with specific fields."""
        from .models import User

        user_id = sample_data["users"][0]
        user = await User.get(user_id, fields=["id", "name", "email"])

        assert user.id == user_id
        assert user.name == "John Doe"
        assert user.email == "john@example.com"

    async def test_table_len(self, sample_data):
        """Test counting records in table."""
        from .models import User

        count = await User.table_len()
        assert count == 2  # sample_data creates 2 users


class TestUpdate:
    """Tests for update operations."""

    async def test_update_single_field(self, sample_data):
        """Test updating single field."""
        from .models import User

        user_id = sample_data["users"][0]
        user = await User.get(user_id)

        await user.update(User(name="John Updated"))

        updated = await User.get(user_id)
        assert updated.name == "John Updated"

    async def test_update_multiple_fields(self, sample_data):
        """Test updating multiple fields."""
        from .models import User

        user_id = sample_data["users"][0]
        user = await User.get(user_id)

        await user.update(
            User(
                name="Completely New Name",
                email="newemail@example.com",
            ),
            fields=["name", "email"],
        )

        updated = await User.get(user_id)
        assert updated.name == "Completely New Name"
        assert updated.email == "newemail@example.com"

    async def test_update_bulk(self, sample_data):
        """Test bulk update."""
        from .models import User

        user_ids = sample_data["users"]
        await User.update_bulk(
            ids=user_ids,
            payload=User(login="bulk_updated"),
        )

        for user_id in user_ids:
            user = await User.get(user_id)
            assert user.login == "bulk_updated"


class TestDelete:
    """Tests for delete operations."""

    async def test_delete_single(self, session, clean_tables):
        """Test deleting single record."""
        from .models import Model

        model_id = await Model.create(Model(name="to_delete"))
        model = await Model.get(model_id)

        await model.delete()

        deleted = await Model.get(model_id)
        assert deleted is None

    async def test_delete_bulk(self, session, clean_tables):
        """Test bulk delete."""
        from .models import Model

        ids = []
        for i in range(5):
            model_id = await Model.create(Model(name=f"model_{i}"))
            ids.append(model_id)

        # Delete first 3
        await Model.delete_bulk(ids[:3])

        # Check deleted
        for deleted_id in ids[:3]:
            assert await Model.get_or_none(deleted_id) is None

        # Check remaining
        for remaining_id in ids[3:]:
            assert await Model.get(remaining_id) is not None


# ====================
# Search Tests
# ====================


class TestSearch:
    """Tests for search operations."""

    async def test_search_all(self, sample_data):
        """Test searching all records."""
        from .models import User

        users = await User.search(fields=["id", "name"])

        assert len(users) == 2

    async def test_search_with_limit(self, sample_data):
        """Test search with limit."""
        from .models import User

        users = await User.search(fields=["id"], limit=1)

        assert len(users) == 1

    async def test_search_with_pagination(self, sample_data):
        """Test search with pagination."""
        from .models import User

        # Get first page
        page1 = await User.search(fields=["id"], start=0, end=1)
        # Get second page
        page2 = await User.search(fields=["id"], start=1, end=2)

        assert len(page1) == 1
        assert len(page2) == 1
        assert page1[0].id != page2[0].id

    async def test_search_with_order_asc(self, sample_data):
        """Test search with ASC order."""
        from .models import User

        users = await User.search(fields=["id", "name"], order="ASC")

        assert users[0].id < users[1].id

    async def test_search_with_order_desc(self, sample_data):
        """Test search with DESC order."""
        from .models import User

        users = await User.search(fields=["id", "name"], order="DESC")

        assert users[0].id > users[1].id

    async def test_search_with_sort_field(self, sample_data):
        """Test search with custom sort field."""
        from .models import User

        users = await User.search(
            fields=["id", "name"], sort="name", order="ASC"
        )

        # Jane comes before John alphabetically
        assert users[0].name == "Jane Smith"
        assert users[1].name == "John Doe"

    async def test_search_with_equality_filter(self, sample_data):
        """Test search with equality filter."""
        from .models import User

        users = await User.search(
            fields=["id", "name"],
            filter=[("name", "=", "John Doe")],
        )

        assert len(users) == 1
        assert users[0].name == "John Doe"

    async def test_search_with_like_filter(self, sample_data):
        """Test search with LIKE filter."""
        from .models import User

        users = await User.search(
            fields=["id", "name"],
            filter=[("email", "like", "example.com")],
        )

        assert len(users) == 2

    async def test_search_with_in_filter(self, sample_data):
        """Test search with IN filter."""
        from .models import User

        user_ids = sample_data["users"]
        users = await User.search(
            fields=["id", "name"],
            filter=[("id", "in", user_ids)],
        )

        assert len(users) == 2

    async def test_search_with_multiple_filters(self, sample_data):
        """Test search with multiple filters (AND)."""
        from .models import User

        users = await User.search(
            fields=["id", "name"],
            filter=[
                ("name", "like", "John"),
                ("email", "like", "example"),
            ],
        )

        assert len(users) == 1
        assert users[0].name == "John Doe"

    async def test_search_with_or_filter(self, sample_data):
        """Test search with OR filter."""
        from .models import User

        users = await User.search(
            fields=["id", "name"],
            filter=[
                ("name", "=", "John Doe"),
                "or",
                ("name", "=", "Jane Smith"),
            ],
        )

        assert len(users) == 2

    async def test_search_empty_result(self, sample_data):
        """Test search with no matching records."""
        from .models import User

        users = await User.search(
            fields=["id"],
            filter=[("name", "=", "Nonexistent User")],
        )

        assert len(users) == 0


# ====================
# Relation Tests
# ====================


class TestMany2oneRelations:
    """Tests for Many2one relations."""

    async def test_create_with_m2o(self, sample_data):
        """Test creating record with M2O relation."""
        from .models import Role, Model

        model_id = sample_data["models"][0]
        role_id = await Role.create(
            Role(
                name="new_role",
                model_id=model_id,
            )
        )

        role = await Role.get(role_id, fields=["id", "name", "model_id"])
        assert role.model_id == model_id

    async def test_search_with_m2o_loaded(self, sample_data):
        """Test search loads M2O relation as object."""
        from .models import Role

        roles = await Role.search(fields=["id", "name", "model_id"])

        assert len(roles) > 0
        # M2O should be loaded as object
        for role in roles:
            if role.model_id:
                assert hasattr(role.model_id, "id")
                assert hasattr(role.model_id, "name")

    async def test_get_fields_nested_m2o(self, sample_data):
        """Test get(fields_nested) loads M2O."""
        from .models import Role

        role_id = sample_data["roles"][0]
        role = await Role.get(
            id=role_id,
            fields=["id", "name", "model_id"],
            fields_nested={"model_id": ["id", "name"]},
        )

        assert role is not None
        assert role.model_id is not None
        assert role.model_id.name == "users"


class TestOne2manyRelations:
    """Tests for One2many relations."""

    async def test_create_o2m_records(self, sample_data):
        """Test creating records for O2M relation."""
        from .models import Role, AccessList

        role_id = sample_data["roles"][0]

        # Create AccessList records linked to Role
        for i in range(3):
            await AccessList.create(
                AccessList(
                    name=f"acl_{i}",
                    role_id=role_id,
                    active=True,
                    perm_read=True,
                )
            )

        # Verify through search
        acls = await AccessList.search(
            fields=["id", "name", "role_id"],
            filter=[("role_id", "=", role_id)],
        )
        assert len(acls) == 3

    async def test_get_fields_nested_o2m(self, sample_data):
        """Test get(fields_nested) loads O2M."""
        from .models import Role, AccessList

        role_id = sample_data["roles"][0]

        # Create ACL records
        await AccessList.create(
            AccessList(
                name="test_acl",
                role_id=role_id,
                active=True,
                perm_read=True,
            )
        )

        role = await Role.get(
            id=role_id,
            fields=["id", "name", "acl_ids"],
            fields_nested={"acl_ids": ["id", "name", "active"]},
        )

        assert role is not None
        # Новый API возвращает список, а не dict
        assert isinstance(role.acl_ids, list)
        assert len(role.acl_ids) >= 1


class TestMany2manyRelations:
    """Tests for Many2many relations."""

    async def test_link_m2m(self, sample_data, session):
        """Test linking M2M records."""
        from .models import User, Role

        user_id = sample_data["users"][0]
        role_ids = sample_data["roles"]

        # Get user
        user = await User.get(user_id)

        # Get M2M field
        role_field = User.get_fields()["role_ids"]

        # Link roles to user
        values = [(user_id, role_id) for role_id in role_ids]
        await User.link_many2many(role_field, values)

        # Verify through get_many2many
        linked_roles = await User.get_many2many(
            id=user_id,
            comodel=Role,
            relation=role_field.many2many_table,
            column1=role_field.column1,
            column2=role_field.column2,
            fields=["id", "name"],
        )

        assert len(linked_roles) == 2

    async def test_unlink_m2m(self, sample_data, session):
        """Test unlinking M2M records."""
        from .models import User, Role

        user_id = sample_data["users"][0]
        role_ids = sample_data["roles"]

        # First link
        role_field = User.get_fields()["role_ids"]
        values = [(user_id, role_id) for role_id in role_ids]
        await User.link_many2many(role_field, values)

        # Then unlink first role
        await User.unlink_many2many(role_field, [role_ids[0]])

        # Verify
        linked_roles = await User.get_many2many(
            id=user_id,
            comodel=Role,
            relation=role_field.many2many_table,
            column1=role_field.column1,
            column2=role_field.column2,
            fields=["id"],
        )

        # Should have only 1 role left
        assert len(linked_roles) == 1

    async def test_get_fields_nested_m2m(self, sample_data, session):
        """Test get(fields_nested) loads M2M."""
        from .models import User, Role

        user_id = sample_data["users"][0]
        role_ids = sample_data["roles"]

        # Link roles
        role_field = User.get_fields()["role_ids"]
        values = [(user_id, role_id) for role_id in role_ids]
        await User.link_many2many(role_field, values)

        # Get with relations
        user = await User.get(
            id=user_id,
            fields=["id", "name", "role_ids"],
            fields_nested={"role_ids": ["id", "name"]},
        )

        assert user is not None
        # Новый API возвращает список, а не dict
        assert isinstance(user.role_ids, list)
        assert len(user.role_ids) == 2


# ====================
# Field Type Tests
# ====================


class TestAllFieldTypes:
    """Tests for all available field types."""

    async def test_integer_fields(self, session, clean_tables):
        """Test integer field types."""
        from .models import AllFieldTypes

        record = AllFieldTypes(
            int_field=42,
            bigint_field=9223372036854775807,  # Max bigint
            smallint_field=32767,  # Max smallint
        )
        record_id = await AllFieldTypes.create(record)

        created = await AllFieldTypes.get(record_id)
        assert created.int_field == 42
        assert created.bigint_field == 9223372036854775807
        assert created.smallint_field == 32767

    async def test_string_fields(self, session, clean_tables):
        """Test string field types."""
        from .models import AllFieldTypes

        record = AllFieldTypes(
            char_field="Short text",
            char_unlimited="Unlimited length text",
            text_field="Very long text " * 100,
        )
        record_id = await AllFieldTypes.create(record)

        created = await AllFieldTypes.get(record_id)
        assert created.char_field == "Short text"
        assert created.char_unlimited == "Unlimited length text"
        assert "Very long text" in created.text_field

    async def test_boolean_fields(self, session, clean_tables):
        """Test boolean field types."""
        from .models import AllFieldTypes

        record = AllFieldTypes(
            bool_field=True,
            bool_default_true=False,  # Override default
            bool_default_false=True,  # Override default
        )
        record_id = await AllFieldTypes.create(record)

        created = await AllFieldTypes.get(record_id)
        assert created.bool_field is True
        assert created.bool_default_true is False
        assert created.bool_default_false is True

    async def test_numeric_fields(self, session, clean_tables):
        """Test numeric field types (Decimal, Float)."""
        from .models import AllFieldTypes

        record = AllFieldTypes(
            decimal_field=Decimal("123.45"),
            float_field=3.14159,
        )
        record_id = await AllFieldTypes.create(record)

        created = await AllFieldTypes.get(record_id)
        assert created.decimal_field == Decimal("123.45")
        assert abs(created.float_field - 3.14159) < 0.0001

    async def test_datetime_fields(self, session, clean_tables):
        """Test date/time field types."""
        from .models import AllFieldTypes

        now = datetime.now()
        today = date.today()
        current_time = time(12, 30, 45)

        record = AllFieldTypes(
            datetime_field=now,
            date_field=today,
            time_field=current_time,
        )
        record_id = await AllFieldTypes.create(record)

        created = await AllFieldTypes.get(record_id)
        assert created.date_field == today
        # Time comparison (ignoring microseconds)
        assert created.time_field.hour == 12
        assert created.time_field.minute == 30

    async def test_json_field(self, session, clean_tables):
        """Test JSON field type."""
        from .models import AllFieldTypes

        json_data = {
            "key": "value",
            "nested": {"a": 1, "b": [1, 2, 3]},
            "array": [1, "two", 3.0],
        }
        record = AllFieldTypes(json_field=json_data)
        record_id = await AllFieldTypes.create(record)

        created = await AllFieldTypes.get(record_id)
        assert created.json_field == json_data
        assert created.json_field["nested"]["a"] == 1

    async def test_binary_field(self, session, clean_tables):
        """Test binary field type."""
        from .models import AllFieldTypes

        binary_data = b"\x00\x01\x02\xff\xfe\xfd"
        record = AllFieldTypes(binary_field=binary_data)
        record_id = await AllFieldTypes.create(record)

        created = await AllFieldTypes.get(record_id)
        assert created.binary_field == binary_data


# ====================
# Constraint Tests
# ====================


class TestConstraints:
    """Tests for database constraints."""

    async def test_unique_constraint(self, session, clean_tables):
        """Test unique constraint violation."""
        import asyncpg
        from .models import UniqueModel

        # Create first record
        await UniqueModel.create(
            UniqueModel(
                code="UNIQUE001",
                name="First",
            )
        )

        # Try to create duplicate
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await UniqueModel.create(
                UniqueModel(
                    code="UNIQUE001",  # Same code
                    name="Second",
                )
            )

    async def test_required_field_constraint(self, session, clean_tables):
        """Test required (NOT NULL) constraint."""
        import asyncpg
        from .models import RequiredFieldsModel

        # Try to create without required field
        with pytest.raises(asyncpg.exceptions.NotNullViolationError):
            await RequiredFieldsModel.create(
                RequiredFieldsModel(
                    required_char="has value",
                    # required_int is missing
                )
            )


# ====================
# Transaction Tests
# ====================


class TestTransactions:
    """Tests for transaction handling."""

    async def test_transaction_commit(self, transaction, clean_tables):
        """Test transaction commit."""
        from .models import Model

        async with transaction as session:
            await session.execute(
                "INSERT INTO models (name) VALUES ($1)",
                ["transaction_test"],
            )

        # Should be committed
        from .models import Model

        models = await Model.search(
            fields=["id", "name"],
            filter=[("name", "=", "transaction_test")],
        )
        assert len(models) == 1

    async def test_transaction_rollback(self, transaction, clean_tables):
        """Test transaction rollback on exception."""
        from .models import Model

        try:
            async with transaction as session:
                await session.execute(
                    "INSERT INTO models (name) VALUES ($1)",
                    ["rollback_test"],
                )
                raise Exception("Force rollback")
        except Exception:
            pass

        # Should be rolled back
        models = await Model.search(
            fields=["id", "name"],
            filter=[("name", "=", "rollback_test")],
        )
        assert len(models) == 0


# ====================
# DDL Tests
# ====================


class TestDDL:
    """Tests for DDL (table creation) operations."""

    async def test_create_table_idempotent(self, session, setup_models):
        """Test that __create_table__ is idempotent."""
        from .models import Model

        # Should not raise error when table already exists
        await Model.__create_table__(session)

    async def test_format_default_value_bool(self):
        """Test formatting boolean default values."""
        from .models import BaseModel

        assert BaseModel.format_default_value(True) == "TRUE"
        assert BaseModel.format_default_value(False) == "FALSE"

    async def test_format_default_value_int(self):
        """Test formatting integer default values."""
        from .models import BaseModel

        assert BaseModel.format_default_value(42) == "42"
        assert BaseModel.format_default_value(0) == "0"
        assert BaseModel.format_default_value(-1) == "-1"

    async def test_format_default_value_string(self):
        """Test formatting string default values."""
        from .models import BaseModel

        assert BaseModel.format_default_value("test") == "'test'"
        assert BaseModel.format_default_value("it's") == "'it''s'"  # Escaped

    async def test_format_default_value_unsafe_raises(self):
        """Test unsafe SQL characters raise error."""
        from .models import BaseModel

        with pytest.raises(ValueError, match="unsafe"):
            BaseModel.format_default_value("test; DROP TABLE users;")


# ====================
# Model Methods Tests
# ====================


class TestModelMethods:
    """Tests for model helper methods."""

    async def test_get_fields(self):
        """Test get_fields returns all fields."""
        from .models import User

        fields = User.get_fields()

        assert "id" in fields
        assert "name" in fields
        assert "email" in fields
        assert "role_ids" in fields

    async def test_get_store_fields(self):
        """Test get_store_fields returns only stored fields."""
        from .models import User

        store_fields = User.get_store_fields()

        assert "id" in store_fields
        assert "name" in store_fields
        # M2M is not stored
        assert "role_ids" not in store_fields

    async def test_get_relation_fields(self):
        """Test get_relation_fields returns relation fields."""
        from .models import User

        rel_fields = User.get_relation_fields()
        field_names = [name for name, _ in rel_fields]

        assert "image" in field_names  # PolymorphicMany2one
        assert "role_ids" in field_names  # Many2many

    async def test_json_serialization(self, sample_data):
        """Test model JSON serialization."""
        from .models import User

        user_id = sample_data["users"][0]
        user = await User.get(user_id)

        json_data = user.json()

        assert isinstance(json_data, dict)
        assert json_data["id"] == user_id
        assert json_data["name"] == "John Doe"

    async def test_json_exclude_fields(self, sample_data):
        """Test JSON serialization with excluded fields."""
        from .models import User

        user_id = sample_data["users"][0]
        user = await User.get(user_id)

        json_data = user.json(exclude={"password_hash", "password_salt"})

        assert "password_hash" not in json_data
        assert "password_salt" not in json_data

    async def test_json_include_fields(self, sample_data):
        """Test JSON serialization with included fields only."""
        from .models import User

        user_id = sample_data["users"][0]
        user = await User.get(user_id)

        json_data = user.json(include={"id", "name"})

        assert "id" in json_data
        assert "name" in json_data
        assert "email" not in json_data


# ====================
# Edge Cases Tests
# ====================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    async def test_empty_search_result(self, session, clean_tables):
        """Test search on empty table."""
        from .models import Model

        models = await Model.search(fields=["id"])
        assert models == []

    async def test_update_nonexistent_record(self, session, clean_tables):
        """Test updating non-existent record."""
        from .models import Model

        # Create a model instance with non-existent ID
        model = Model(name="test")
        model.id = 99999

        # Should not raise, just update nothing
        await model.update(Model(name="updated"))

    async def test_search_with_empty_fields(self, sample_data):
        """Test search defaults to ['id'] when fields not specified."""
        from .models import User

        users = await User.search()  # No fields specified

        assert len(users) > 0
        assert hasattr(users[0], "id")

    async def test_special_characters_in_string(self, session, clean_tables):
        """Test handling special characters in strings."""
        from .models import Model

        special_name = 'Test\'s "special" name with <>&'
        model_id = await Model.create(Model(name=special_name))

        created = await Model.get(model_id)
        assert created.name == special_name

    async def test_unicode_strings(self, session, clean_tables):
        """Test handling unicode strings."""
        from .models import Model

        unicode_name = "Тест Unicode 日本語 🎉"
        model_id = await Model.create(Model(name=unicode_name))

        created = await Model.get(model_id)
        assert created.name == unicode_name

    async def test_null_in_json_field(self, session, clean_tables):
        """Test NULL in JSON field."""
        from .models import AllFieldTypes

        record = AllFieldTypes(json_field=None)
        record_id = await AllFieldTypes.create(record)

        created = await AllFieldTypes.get(record_id)
        assert created.json_field is None

    async def test_empty_json_object(self, session, clean_tables):
        """Test empty JSON object."""
        from .models import AllFieldTypes

        record = AllFieldTypes(json_field={})
        record_id = await AllFieldTypes.create(record)

        created = await AllFieldTypes.get(record_id)
        assert created.json_field == {}

    async def test_empty_json_array(self, session, clean_tables):
        """Test empty JSON array."""
        from .models import AllFieldTypes

        record = AllFieldTypes(json_field=[])
        record_id = await AllFieldTypes.create(record)

        created = await AllFieldTypes.get(record_id)
        assert created.json_field == []
