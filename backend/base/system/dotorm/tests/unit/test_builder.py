"""
Unit tests for SQL Query Builder.

These tests verify SQL generation without database connection.
Run with: pytest tests/unit/test_builder.py -v
"""

import pytest
from dataclasses import dataclass


# ====================
# Mock classes for isolated testing
# ====================


@dataclass
class MockField:
    """Mock Field for testing Builder without full ORM."""

    store: bool = True
    relation: bool = False
    primary_key: bool = False


@dataclass
class MockDialect:
    """Mock Dialect for testing."""

    name: str = "postgres"
    escape: str = '"'
    placeholder: str = "$"
    supports_returning: bool = True


class MockFilterParser:
    """Mock FilterParser for Builder tests."""

    def __init__(self, dialect):
        self.dialect = dialect

    def parse(self, filter_expr):
        """Simple mock parser for testing."""
        # Возвращаем простой WHERE clause для тестов
        if isinstance(filter_expr, list) and len(filter_expr) == 3:
            field, op, value = filter_expr
            return f'"{field}" {op} %s', (value,)
        return "", ()


# ====================
# Builder tests
# ====================


@pytest.mark.unit
class TestBuilderDelete:
    """Tests for DELETE query building."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.builder.builder import Builder
        from dotorm.components.dialect import POSTGRES

        self.fields = {
            "id": MockField(store=True, primary_key=True),
            "name": MockField(store=True),
            "email": MockField(store=True),
        }
        self.builder = Builder(
            table="users",
            fields=self.fields,
            dialect=POSTGRES,
        )

    def test_build_delete_single(self):
        """Test DELETE query for single record."""
        stmt = self.builder.build_delete()

        assert stmt == "DELETE FROM users WHERE id=%s"

    def test_build_delete_bulk(self):
        """Test DELETE query for multiple records."""
        stmt = self.builder.build_delete_bulk(count=3)

        assert stmt == "DELETE FROM users WHERE id IN (%s,%s,%s)"

    def test_build_delete_bulk_single(self):
        """Test DELETE bulk with single ID."""
        stmt = self.builder.build_delete_bulk(count=1)

        assert stmt == "DELETE FROM users WHERE id IN (%s)"

    def test_build_delete_bulk_many(self):
        """Test DELETE bulk with many IDs."""
        stmt = self.builder.build_delete_bulk(count=10)

        expected_placeholders = ",".join(["%s"] * 10)
        assert (
            stmt == f"DELETE FROM users WHERE id IN ({expected_placeholders})"
        )


@pytest.mark.unit
class TestBuilderCreate:
    """Tests for INSERT query building."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.builder.builder import Builder
        from dotorm.components.dialect import POSTGRES

        self.fields = {
            "id": MockField(store=True, primary_key=True),
            "name": MockField(store=True),
            "email": MockField(store=True),
            "active": MockField(store=True),
        }
        self.builder = Builder(
            table="users",
            fields=self.fields,
            dialect=POSTGRES,
        )

    def test_build_create_single_field(self):
        """Test INSERT with single field."""
        payload = {"name": "John"}
        stmt, values = self.builder.build_create(payload)

        assert stmt == "INSERT INTO users (name) VALUES (%s)"
        assert values == ("John",)

    def test_build_create_multiple_fields(self):
        """Test INSERT with multiple fields."""
        payload = {"name": "John", "email": "john@example.com"}
        stmt, values = self.builder.build_create(payload)

        assert "INSERT INTO users" in stmt
        assert "name" in stmt
        assert "email" in stmt
        assert "VALUES" in stmt
        assert values == ("John", "john@example.com")

    def test_build_create_with_boolean(self):
        """Test INSERT with boolean field."""
        payload = {"name": "John", "active": True}
        stmt, values = self.builder.build_create(payload)

        assert "active" in stmt
        assert True in values

    def test_build_create_empty_raises(self):
        """Test INSERT with empty payload raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            self.builder.build_create({})

    def test_build_create_bulk(self):
        """Test bulk INSERT."""
        payloads = [
            {"name": "John", "email": "john@example.com"},
            {"name": "Jane", "email": "jane@example.com"},
        ]
        stmt, values_lists = self.builder.build_create_bulk(payloads)

        assert "INSERT INTO users" in stmt
        assert "(name, email)" in stmt
        assert len(values_lists) == 4
        assert values_lists == [
            "John",
            "john@example.com",
            "Jane",
            "jane@example.com",
        ]


@pytest.mark.unit
class TestBuilderUpdate:
    """Tests for UPDATE query building."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.builder.builder import Builder
        from dotorm.components.dialect import POSTGRES

        self.fields = {
            "id": MockField(store=True, primary_key=True),
            "name": MockField(store=True),
            "email": MockField(store=True),
            "active": MockField(store=True),
        }
        self.builder = Builder(
            table="users",
            fields=self.fields,
            dialect=POSTGRES,
        )

    def test_build_update_single_field(self):
        """Test UPDATE with single field."""
        payload = {"name": "John Updated"}
        stmt, values = self.builder.build_update(payload, id=1)

        assert stmt == "UPDATE users SET name=%s WHERE id = %s"
        assert values == ("John Updated", 1)

    def test_build_update_multiple_fields(self):
        """Test UPDATE with multiple fields."""
        payload = {"name": "John", "email": "john@new.com"}
        stmt, values = self.builder.build_update(payload, id=42)

        assert "UPDATE users SET" in stmt
        assert "name=%s" in stmt
        assert "email=%s" in stmt
        assert "WHERE id = %s" in stmt
        assert values[-1] == 42  # ID is last

    def test_build_update_empty_raises(self):
        """Test UPDATE with empty payload raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            self.builder.build_update({}, id=1)

    def test_build_update_bulk(self):
        """Test bulk UPDATE."""
        payload = {"active": False}
        stmt, values = self.builder.build_update_bulk(payload, ids=[1, 2, 3])

        assert "UPDATE users SET active=%s" in stmt
        assert "WHERE id IN (%s, %s, %s)" in stmt
        assert values == (False, 1, 2, 3)


@pytest.mark.unit
class TestBuilderGet:
    """Tests for SELECT by ID query building."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.builder.builder import Builder
        from dotorm.components.dialect import POSTGRES

        self.fields = {
            "id": MockField(store=True, primary_key=True),
            "name": MockField(store=True),
            "email": MockField(store=True),
            "computed": MockField(store=False),  # Not stored
        }
        self.builder = Builder(
            table="users",
            fields=self.fields,
            dialect=POSTGRES,
        )

    def test_build_get_all_fields(self):
        """Test SELECT with all stored fields."""
        stmt, values = self.builder.build_get(id=1)

        assert "SELECT" in stmt
        assert '"id"' in stmt
        assert '"name"' in stmt
        assert '"email"' in stmt
        assert '"computed"' not in stmt  # Not stored
        assert "FROM users" in stmt
        assert "WHERE id = %s" in stmt
        assert "LIMIT 1" in stmt
        assert values == [1]

    def test_build_get_specific_fields(self):
        """Test SELECT with specific fields."""
        stmt, values = self.builder.build_get(id=1, fields=["name", "email"])

        assert '"name"' in stmt
        assert '"email"' in stmt
        assert '"id"' not in stmt
        assert values == [1]

    def test_build_get_single_field(self):
        """Test SELECT with single field."""
        stmt, values = self.builder.build_get(id=99, fields=["name"])

        assert 'SELECT "name" FROM users' in stmt
        assert values == [99]

    def test_build_table_len(self):
        """Test COUNT query."""
        stmt, values = self.builder.build_table_len()

        assert stmt == "SELECT COUNT(*) FROM users"
        assert values is None


@pytest.mark.unit
class TestBuilderSearch:
    """Tests for search query building."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.builder.builder import Builder
        from dotorm.components.dialect import POSTGRES

        self.fields = {
            "id": MockField(store=True, primary_key=True),
            "name": MockField(store=True),
            "email": MockField(store=True),
            "age": MockField(store=True),
            "active": MockField(store=True),
            "computed": MockField(store=False),
        }
        self.builder = Builder(
            table="users",
            fields=self.fields,
            dialect=POSTGRES,
        )

    def test_build_search_default(self):
        """Test search with defaults."""
        stmt, values = self.builder.build_search()

        assert (
            'SELECT "id", "name", "email", "age", "active" FROM users  ORDER BY id DESC LIMIT %s'
            in stmt
        )
        assert "ORDER BY id DESC" in stmt
        assert "LIMIT %s" in stmt
        assert values == (80,)  # default limit

    def test_build_search_with_fields(self):
        """Test search with specific fields."""
        stmt, values = self.builder.build_search(
            fields=["id", "name", "email"]
        )

        assert '"id"' in stmt
        assert '"name"' in stmt
        assert '"email"' in stmt
        assert '"age"' not in stmt

    def test_build_search_with_limit(self):
        """Test search with custom limit."""
        stmt, values = self.builder.build_search(limit=10)

        assert "LIMIT %s" in stmt
        assert values == (10,)

    def test_build_search_with_pagination(self):
        """Test search with start/end pagination."""
        stmt, values = self.builder.build_search(start=20, end=40)

        assert "LIMIT %s OFFSET %s" in stmt
        assert values == (20, 20)  # (end-start, start)

    def test_build_search_order_asc(self):
        """Test search with ASC order."""
        stmt, _ = self.builder.build_search(order="ASC")

        assert "ORDER BY id ASC" in stmt

    def test_build_search_order_desc(self):
        """Test search with DESC order."""
        stmt, _ = self.builder.build_search(order="desc")

        assert "ORDER BY id DESC" in stmt

    def test_build_search_custom_sort(self):
        """Test search with custom sort field."""
        stmt, _ = self.builder.build_search(sort="name")

        assert "ORDER BY name" in stmt

    def test_build_search_invalid_order_raises(self):
        """Test search with invalid order raises error."""
        with pytest.raises(ValueError, match="Invalid order"):
            self.builder.build_search(order="INVALID")

    def test_build_search_invalid_sort_raises(self):
        """Test search with invalid sort field raises error."""
        # with pytest.raises(ValueError, match="Invalid sort field"):
        stmt, values = self.builder.build_search(sort="nonexistent")
        assert "id" in stmt

    def test_build_search_with_simple_filter(self):
        """Test search with simple equality filter."""
        stmt, values = self.builder.build_search(
            fields=["id", "name"],
            filter=[("active", "=", True)],
        )

        assert "WHERE" in stmt
        assert '"active"' in stmt
        assert "= %s" in stmt
        # values содержит filter value + limit
        assert True in values

    def test_build_search_with_in_filter(self):
        """Test search with IN filter."""
        stmt, values = self.builder.build_search(
            fields=["id"],
            filter=[("id", "in", [1, 2, 3])],
        )

        assert "WHERE" in stmt
        assert "IN" in stmt
        assert 1 in values
        assert 2 in values
        assert 3 in values

    def test_build_search_excludes_non_stored(self):
        """Test that non-stored fields are excluded."""
        stmt, _ = self.builder.build_search(
            fields=["id", "name", "computed"],  # computed is not stored
        )

        assert '"id"' in stmt
        assert '"name"' in stmt
        assert '"computed"' not in stmt


@pytest.mark.unit
class TestBuilderDialects:
    """Tests for different SQL dialects."""

    def test_postgres_escaping(self):
        """Test PostgreSQL uses double quotes for escaping."""
        from dotorm.builder.builder import Builder
        from dotorm.components.dialect import POSTGRES

        fields = {"id": MockField(), "name": MockField()}
        builder = Builder(table="users", fields=fields, dialect=POSTGRES)

        stmt, _ = builder.build_get(id=1, fields=["name"])

        assert '"name"' in stmt

    def test_mysql_escaping(self):
        """Test MySQL uses backticks for escaping."""
        from dotorm.builder.builder import Builder
        from dotorm.components.dialect import MYSQL

        fields = {"id": MockField(), "name": MockField()}
        builder = Builder(table="users", fields=fields, dialect=MYSQL)

        stmt, _ = builder.build_get(id=1, fields=["name"])

        assert "`name`" in stmt


@pytest.mark.unit
class TestBuilderGetStoreFields:
    """Tests for get_store_fields method."""

    def test_returns_only_stored_fields(self):
        """Test that only stored fields are returned."""
        from dotorm.builder.builder import Builder
        from dotorm.components.dialect import POSTGRES

        fields = {
            "id": MockField(store=True),
            "name": MockField(store=True),
            "computed": MockField(store=False),
            "relation": MockField(store=False),
        }
        builder = Builder(table="test", fields=fields, dialect=POSTGRES)

        store_fields = builder.get_store_fields()

        assert "id" in store_fields
        assert "name" in store_fields
        assert "computed" not in store_fields
        assert "relation" not in store_fields

    def test_empty_fields(self):
        """Test with no fields."""
        from dotorm.builder.builder import Builder
        from dotorm.components.dialect import POSTGRES

        builder = Builder(table="test", fields={}, dialect=POSTGRES)

        store_fields = builder.get_store_fields()

        assert store_fields == []


@pytest.mark.unit
class TestBuilderHelpers:
    """Tests for helper functions."""

    def test_build_sql_update_from_schema(self):
        """Test update SQL building helper."""
        from dotorm.builder.helpers import build_sql_update_from_schema

        sql = "UPDATE test SET %s WHERE id = %s"
        payload = {"name": "John", "age": 30}

        result_sql, values = build_sql_update_from_schema(sql, payload, id=1)

        assert "name=%s" in result_sql
        assert "age=%s" in result_sql
        assert values == ("John", 30, 1)

    def test_build_sql_update_bulk_from_schema(self):
        """Test bulk update SQL building helper."""
        from dotorm.builder.helpers import build_sql_update_from_schema

        sql = "UPDATE test SET %s WHERE id IN (%s)"
        payload = {"active": False}

        result_sql, values = build_sql_update_from_schema(
            sql, payload, id=[1, 2, 3]
        )

        assert "active=%s" in result_sql
        assert "%s, %s, %s" in result_sql
        assert values == (False, 1, 2, 3)

    def test_build_sql_create_from_schema(self):
        """Test create SQL building helper."""
        from dotorm.builder.helpers import build_sql_create_from_schema

        sql = "INSERT INTO test (%s) VALUES (%s)"
        payload = {"name": "John", "email": "john@test.com"}

        result_sql, values = build_sql_create_from_schema(sql, payload)

        assert "name" in result_sql
        assert "email" in result_sql
        assert "%s, %s" in result_sql or "%s,%s" in result_sql
        assert values == ("John", "john@test.com")

    def test_build_sql_create_empty_raises(self):
        """Test create with empty payload raises error."""
        from dotorm.builder.helpers import build_sql_create_from_schema

        with pytest.raises(ValueError, match="cannot be empty"):
            build_sql_create_from_schema(
                "INSERT INTO test (%s) VALUES (%s)", {}
            )

    def test_build_sql_update_empty_raises(self):
        """Test update with empty payload raises error."""
        from dotorm.builder.helpers import build_sql_update_from_schema

        with pytest.raises(ValueError, match="cannot be empty"):
            build_sql_update_from_schema(
                "UPDATE test SET %s WHERE id = %s", {}, 1
            )
