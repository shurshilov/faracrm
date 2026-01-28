"""
Pytest configuration and shared fixtures.

This file is automatically loaded by pytest.
"""

import pytest
from dataclasses import dataclass


# ====================
# Mock Field classes for unit tests
# ====================

@dataclass
class MockField:
    """Mock Field for testing Builder without full ORM."""
    store: bool = True
    relation: bool = False
    primary_key: bool = False
    null: bool = True


def create_mock_fields() -> dict[str, MockField]:
    """Create mock fields for testing."""
    return {
        "id": MockField(store=True, primary_key=True),
        "name": MockField(store=True),
        "email": MockField(store=True),
        "active": MockField(store=True),
        "age": MockField(store=True),
        "role_id": MockField(store=True, relation=True),
        # Non-stored field (like computed or x2many)
        "computed_field": MockField(store=False),
    }


@pytest.fixture
def mock_fields():
    """Fixture providing mock fields."""
    return create_mock_fields()


# ====================
# Dialect fixtures
# ====================

@pytest.fixture
def postgres_dialect():
    """PostgreSQL dialect fixture."""
    # Импорт здесь чтобы не требовать dotorm для unit тестов
    from dotorm.components.dialect import POSTGRES
    return POSTGRES


@pytest.fixture
def mysql_dialect():
    """MySQL dialect fixture."""
    from dotorm.components.dialect import MYSQL
    return MYSQL
