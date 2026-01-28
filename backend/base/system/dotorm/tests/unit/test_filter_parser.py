"""
Unit tests for SQL Filter Parser.

These tests verify filter expression parsing without database connection.
Run with: pytest tests/unit/test_filter_parser.py -v
"""

import pytest


@pytest.mark.unit
class TestFilterParserSimpleTriplets:
    """Tests for simple filter triplets (field, operator, value)."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.components.filter_parser import FilterParser
        from dotorm.components.dialect import POSTGRES

        self.parser = FilterParser(POSTGRES)

    def test_equality_operator(self):
        """Test equality operator."""
        clause, values = self.parser.parse(("name", "=", "John"))

        assert clause == '"name" = %s'
        assert values == ("John",)

    def test_not_equal_operator(self):
        """Test not equal operator."""
        clause, values = self.parser.parse(("status", "!=", "deleted"))

        assert clause == '"status" != %s'
        assert values == ("deleted",)

    def test_greater_than_operator(self):
        """Test greater than operator."""
        clause, values = self.parser.parse(("age", ">", 18))

        assert clause == '"age" > %s'
        assert values == (18,)

    def test_less_than_operator(self):
        """Test less than operator."""
        clause, values = self.parser.parse(("price", "<", 100))

        assert clause == '"price" < %s'
        assert values == (100,)

    def test_greater_or_equal_operator(self):
        """Test greater than or equal operator."""
        clause, values = self.parser.parse(("count", ">=", 5))

        assert clause == '"count" >= %s'
        assert values == (5,)

    def test_less_or_equal_operator(self):
        """Test less than or equal operator."""
        clause, values = self.parser.parse(("rating", "<=", 10))

        assert clause == '"rating" <= %s'
        assert values == (10,)

    def test_boolean_value(self):
        """Test with boolean value."""
        clause, values = self.parser.parse(("active", "=", True))

        assert clause == '"active" = %s'
        assert values == (True,)

    def test_none_value(self):
        """Test with None value."""
        clause, values = self.parser.parse(("deleted_at", "=", None))

        assert clause == '"deleted_at" = %s'
        assert values == (None,)

    def test_integer_value(self):
        """Test with integer value."""
        clause, values = self.parser.parse(("id", "=", 42))

        assert clause == '"id" = %s'
        assert values == (42,)

    def test_float_value(self):
        """Test with float value."""
        clause, values = self.parser.parse(("price", "=", 99.99))

        assert clause == '"price" = %s'
        assert values == (99.99,)


@pytest.mark.unit
class TestFilterParserInOperators:
    """Tests for IN and NOT IN operators."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.components.filter_parser import FilterParser
        from dotorm.components.dialect import POSTGRES

        self.parser = FilterParser(POSTGRES)

    def test_in_operator_list(self):
        """Test IN operator with list."""
        clause, values = self.parser.parse(("id", "in", [1, 2, 3]))

        assert clause == '"id" IN (%s, %s, %s)'
        assert values == (1, 2, 3)

    def test_in_operator_tuple(self):
        """Test IN operator with tuple."""
        clause, values = self.parser.parse(("status", "in", ("active", "pending")))

        assert clause == '"status" IN (%s, %s)'
        assert values == ("active", "pending")

    def test_not_in_operator(self):
        """Test NOT IN operator."""
        clause, values = self.parser.parse(("role", "not in", ["admin", "guest"]))

        assert clause == '"role" NOT IN (%s, %s)'
        assert values == ("admin", "guest")

    def test_in_single_value(self):
        """Test IN with single value."""
        clause, values = self.parser.parse(("id", "in", [42]))

        assert clause == '"id" IN (%s)'
        assert values == (42,)

    def test_in_many_values(self):
        """Test IN with many values."""
        ids = list(range(10))
        clause, values = self.parser.parse(("id", "in", ids))

        placeholders = ", ".join(["%s"] * 10)
        assert clause == f'"id" IN ({placeholders})'
        assert values == tuple(ids)

    def test_in_non_list_raises(self):
        """Test IN with non-list value raises error."""
        with pytest.raises(ValueError, match="requires list/tuple"):
            self.parser.parse(("id", "in", 42))


@pytest.mark.unit
class TestFilterParserLikeOperators:
    """Tests for LIKE and ILIKE operators."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.components.filter_parser import FilterParser
        from dotorm.components.dialect import POSTGRES

        self.parser = FilterParser(POSTGRES)

    def test_like_operator(self):
        """Test LIKE operator."""
        clause, values = self.parser.parse(("name", "like", "John"))

        assert clause == '"name" LIKE %s'
        assert values == ("%John%",)  # Wrapped with %

    def test_ilike_operator(self):
        """Test ILIKE operator (case-insensitive)."""
        clause, values = self.parser.parse(("email", "ilike", "gmail"))

        assert clause == '"email" ILIKE %s'
        assert values == ("%gmail%",)

    def test_not_like_operator(self):
        """Test NOT LIKE operator."""
        clause, values = self.parser.parse(("name", "not like", "test"))

        assert clause == '"name" NOT LIKE %s'
        assert values == ("%test%",)

    def test_not_ilike_operator(self):
        """Test NOT ILIKE operator."""
        clause, values = self.parser.parse(("email", "not ilike", "spam"))

        assert clause == '"email" NOT ILIKE %s'
        assert values == ("%spam%",)

    def test_equals_like_operator(self):
        """Test =like operator (Odoo style)."""
        clause, values = self.parser.parse(("code", "=like", "ABC"))

        assert clause == '"code" =LIKE %s'
        assert values == ("%ABC%",)

    def test_equals_ilike_operator(self):
        """Test =ilike operator (Odoo style)."""
        clause, values = self.parser.parse(("code", "=ilike", "abc"))

        assert clause == '"code" =ILIKE %s'
        assert values == ("%abc%",)


@pytest.mark.unit
class TestFilterParserNullOperators:
    """Tests for IS NULL and IS NOT NULL operators."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.components.filter_parser import FilterParser
        from dotorm.components.dialect import POSTGRES

        self.parser = FilterParser(POSTGRES)

    def test_is_null_operator(self):
        """Test IS NULL operator."""
        clause, values = self.parser.parse(("deleted_at", "is null", None))

        assert clause == '"deleted_at" IS NULL'
        assert values == ()

    def test_is_not_null_operator(self):
        """Test IS NOT NULL operator."""
        clause, values = self.parser.parse(("email", "is not null", None))

        assert clause == '"email" IS NOT NULL'
        assert values == ()

    def test_is_null_any_value(self):
        """Test IS NULL ignores the value."""
        clause, values = self.parser.parse(("field", "is null", "ignored"))

        assert clause == '"field" IS NULL'
        assert values == ()


@pytest.mark.unit
class TestFilterParserBetweenOperators:
    """Tests for BETWEEN and NOT BETWEEN operators."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.components.filter_parser import FilterParser
        from dotorm.components.dialect import POSTGRES

        self.parser = FilterParser(POSTGRES)

    def test_between_operator(self):
        """Test BETWEEN operator."""
        clause, values = self.parser.parse(("age", "between", [18, 65]))

        assert clause == '"age" BETWEEN %s AND %s'
        assert values == (18, 65)

    def test_not_between_operator(self):
        """Test NOT BETWEEN operator."""
        clause, values = self.parser.parse(("price", "not between", [0, 10]))

        assert clause == '"price" NOT BETWEEN %s AND %s'
        assert values == (0, 10)

    def test_between_with_dates(self):
        """Test BETWEEN with date strings."""
        clause, values = self.parser.parse(
            ("created_at", "between", ["2024-01-01", "2024-12-31"])
        )

        assert clause == '"created_at" BETWEEN %s AND %s'
        assert values == ("2024-01-01", "2024-12-31")

    def test_between_wrong_length_raises(self):
        """Test BETWEEN with wrong number of values raises error."""
        with pytest.raises(ValueError, match="requires list of two values"):
            self.parser.parse(("age", "between", [18]))

    def test_between_non_list_raises(self):
        """Test BETWEEN with non-list value raises error."""
        with pytest.raises(ValueError, match="requires list of two values"):
            self.parser.parse(("age", "between", 18))


@pytest.mark.unit
class TestFilterParserNotExpression:
    """Tests for NOT expressions."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.components.filter_parser import FilterParser
        from dotorm.components.dialect import POSTGRES

        self.parser = FilterParser(POSTGRES)

    def test_not_simple_expression(self):
        """Test NOT with simple expression."""
        clause, values = self.parser.parse(("not", ("active", "=", True)))

        assert clause == 'NOT ("active" = %s)'
        assert values == (True,)

    def test_not_in_expression(self):
        """Test NOT with IN expression."""
        clause, values = self.parser.parse(("not", ("id", "in", [1, 2, 3])))

        assert clause == 'NOT ("id" IN (%s, %s, %s))'
        assert values == (1, 2, 3)


@pytest.mark.unit
class TestFilterParserComplexExpressions:
    """Tests for complex nested filter expressions."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.components.filter_parser import FilterParser
        from dotorm.components.dialect import POSTGRES

        self.parser = FilterParser(POSTGRES)

    def test_two_conditions_implicit_and(self):
        """Test two conditions with implicit AND."""
        clause, values = self.parser.parse([
            ("active", "=", True),
            ("age", ">", 18),
        ])

        assert '"active" = %s' in clause
        assert '"age" > %s' in clause
        assert "AND" in clause
        assert values == (True, 18)

    def test_two_conditions_explicit_and(self):
        """Test two conditions with explicit AND."""
        clause, values = self.parser.parse([
            ("active", "=", True),
            "and",
            ("age", ">", 18),
        ])

        assert '"active" = %s' in clause
        assert '"age" > %s' in clause
        assert "AND" in clause
        assert values == (True, 18)

    def test_two_conditions_or(self):
        """Test two conditions with OR."""
        clause, values = self.parser.parse([
            ("role", "=", "admin"),
            "or",
            ("role", "=", "superuser"),
        ])

        assert '"role" = %s' in clause
        assert "OR" in clause
        assert values == ("admin", "superuser")

    def test_three_conditions_mixed(self):
        """Test three conditions with mixed operators."""
        clause, values = self.parser.parse([
            ("active", "=", True),
            "and",
            ("role", "=", "admin"),
            "or",
            ("is_superuser", "=", True),
        ])

        assert "AND" in clause
        assert "OR" in clause
        assert values == (True, "admin", True)

    def test_nested_or_in_and(self):
        """Test nested OR within AND."""
        clause, values = self.parser.parse([
            ("active", "=", True),
            "and",
            [
                ("role", "=", "admin"),
                "or",
                ("role", "=", "moderator"),
            ],
        ])

        assert "AND" in clause
        assert "OR" in clause
        # Nested expression should be wrapped in parentheses
        assert "(" in clause
        assert values == (True, "admin", "moderator")

    def test_nested_and_in_or(self):
        """Test nested AND within OR."""
        clause, values = self.parser.parse([
            [
                ("active", "=", True),
                ("verified", "=", True),
            ],
            "or",
            ("is_admin", "=", True),
        ])

        assert "AND" in clause
        assert "OR" in clause
        assert values == (True, True, True)

    def test_multiple_nested_groups(self):
        """Test multiple nested groups."""
        clause, values = self.parser.parse([
            [
                ("country", "=", "US"),
                ("state", "=", "CA"),
            ],
            "or",
            [
                ("country", "=", "UK"),
                ("city", "=", "London"),
            ],
        ])

        # Should have two groups with parentheses
        assert clause.count("(") >= 2
        assert "OR" in clause
        assert values == ("US", "CA", "UK", "London")


@pytest.mark.unit
class TestFilterParserEdgeCases:
    """Tests for edge cases and error handling."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.components.filter_parser import FilterParser
        from dotorm.components.dialect import POSTGRES

        self.parser = FilterParser(POSTGRES)

    def test_unsupported_operator_raises(self):
        """Test unsupported operator raises error."""
        with pytest.raises(ValueError, match="Unsupported operator"):
            self.parser.parse(("field", "invalid_op", "value"))

    def test_invalid_filter_element_raises(self):
        """Test invalid filter element raises error."""
        with pytest.raises(ValueError, match="Invalid filter element"):
            self.parser.parse([("valid", "=", 1), 123, ("also_valid", "=", 2)])

    def test_operator_case_insensitive(self):
        """Test operators are case-insensitive."""
        clause1, _ = self.parser.parse(("field", "LIKE", "test"))
        clause2, _ = self.parser.parse(("field", "like", "test"))
        clause3, _ = self.parser.parse(("field", "Like", "test"))

        assert "LIKE" in clause1
        assert "LIKE" in clause2
        assert "LIKE" in clause3

    def test_empty_in_list(self):
        """Test IN with empty list."""
        clause, values = self.parser.parse(("id", "in", []))

        assert clause == '"id" IN ()'
        assert values == ()

    def test_field_with_special_chars(self):
        """Test field name is properly escaped."""
        clause, values = self.parser.parse(("user_name", "=", "test"))

        assert '"user_name"' in clause


@pytest.mark.unit
class TestFilterParserDialects:
    """Tests for different SQL dialects."""

    def test_postgres_escaping(self):
        """Test PostgreSQL uses double quotes."""
        from dotorm.components.filter_parser import FilterParser
        from dotorm.components.dialect import POSTGRES

        parser = FilterParser(POSTGRES)
        clause, _ = parser.parse(("name", "=", "test"))

        assert '"name"' in clause

    def test_mysql_escaping(self):
        """Test MySQL uses backticks."""
        from dotorm.components.filter_parser import FilterParser
        from dotorm.components.dialect import MYSQL

        parser = FilterParser(MYSQL)
        clause, _ = parser.parse(("name", "=", "test"))

        assert "`name`" in clause


@pytest.mark.unit
class TestFilterParserOdooCompatibility:
    """Tests for Odoo-style filter expressions."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.components.filter_parser import FilterParser
        from dotorm.components.dialect import POSTGRES

        self.parser = FilterParser(POSTGRES)

    def test_odoo_style_domain(self):
        """Test Odoo-style domain expression."""
        # Odoo: [('active', '=', True), ('name', 'ilike', 'test')]
        clause, values = self.parser.parse([
            ("active", "=", True),
            ("name", "ilike", "test"),
        ])

        assert '"active" = %s' in clause
        assert '"name" ILIKE %s' in clause
        assert "AND" in clause

    def test_odoo_style_or_domain(self):
        """Test Odoo-style OR domain."""
        # Odoo: ['|', ('state', '=', 'draft'), ('state', '=', 'confirmed')]
        clause, values = self.parser.parse([
            ("state", "=", "draft"),
            "or",
            ("state", "=", "confirmed"),
        ])

        assert "OR" in clause

    def test_odoo_style_not_domain(self):
        """Test Odoo-style NOT domain."""
        clause, values = self.parser.parse(
            ("not", ("active", "=", False))
        )

        assert "NOT" in clause


@pytest.mark.unit
class TestFilterParserIsTriplet:
    """Tests for _is_triplet helper method."""

    def setup_method(self):
        """Setup test fixtures."""
        from dotorm.components.filter_parser import FilterParser
        from dotorm.components.dialect import POSTGRES

        self.parser = FilterParser(POSTGRES)

    def test_valid_triplet_tuple(self):
        """Test valid triplet as tuple."""
        assert self.parser._is_triplet(("field", "=", "value")) is True

    def test_valid_triplet_list(self):
        """Test valid triplet as list."""
        assert self.parser._is_triplet(["field", "=", "value"]) is True

    def test_invalid_triplet_wrong_length(self):
        """Test invalid triplet with wrong length."""
        assert self.parser._is_triplet(("field", "=")) is False
        assert self.parser._is_triplet(("field", "=", "value", "extra")) is False

    def test_invalid_triplet_non_string_field(self):
        """Test invalid triplet with non-string field."""
        assert self.parser._is_triplet((123, "=", "value")) is False

    def test_invalid_triplet_not_sequence(self):
        """Test invalid triplet that is not a sequence."""
        assert self.parser._is_triplet("not a triplet") is False
        assert self.parser._is_triplet(123) is False
