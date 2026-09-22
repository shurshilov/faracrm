"""
ВРЕМЕННО — УДАЛИТЬ вместе с _migrate_like_expr в
backend/base/system/saved_filters/app.py.

like/ilike теперь ищут подстроку и экранируют % и _; сохранённые раньше
фильтры со своим шаблоном переводятся на =like/=ilike (шаблон как есть),
у not like/not ilike снимаются обрамляющие %.

No database.
"""

import pytest

from backend.base.system.saved_filters.app import _migrate_like_expr

pytestmark = pytest.mark.unit


def test_ilike_with_own_wildcards_becomes_raw_pattern():
    expr = [["name", "ilike", "%test%"]]
    assert _migrate_like_expr(expr) is True
    assert expr == [["name", "=ilike", "%test%"]]


def test_prefix_pattern_keeps_old_substring_semantics():
    # раньше парсер сам оборачивал в %…%: "acme%" искал подстроку acme
    expr = [["name", "like", "acme%"]]
    assert _migrate_like_expr(expr) is True
    assert expr == [["name", "=like", "%acme%"]]


def test_not_ilike_strips_outer_percents():
    expr = [["name", "not ilike", "%spam%"]]
    assert _migrate_like_expr(expr) is True
    assert expr == [["name", "not ilike", "spam"]]


def test_plain_substring_untouched():
    expr = [["name", "ilike", "acme"], "or", ["login", "=", "50%"]]
    assert _migrate_like_expr(expr) is False
    assert expr == [["name", "ilike", "acme"], "or", ["login", "=", "50%"]]


def test_nested_and_not_groups():
    expr = [
        ["active", "=", True],
        ["not", [["name", "ilike", "%old%"], "or", ["code", "like", "%x%"]]],
    ]
    assert _migrate_like_expr(expr) is True
    assert expr == [
        ["active", "=", True],
        ["not", [["name", "=ilike", "%old%"], "or", ["code", "=like", "%x%"]]],
    ]


def test_idempotent():
    expr = [["name", "ilike", "%test%"], ["name", "not like", "%a%"]]
    _migrate_like_expr(expr)
    assert _migrate_like_expr(expr) is False
