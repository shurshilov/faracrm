"""
Unit-тесты билдера связей (builder/mixins/m2m.py, builder/mixins/relations.py).

Контракт (аудит билдера 2026-09-22):
- build_get_many2many: LIMIT только явный — дефолт limit=None (скрытый
  LIMIT 10 молча обрезал связи у вызывающих без лимита); ORDER BY с алиасом
  p.{sort} — без него «id» неоднозначен между p и t, когда его нет в SELECT;
- build_get_many2many_multiple: без LIMIT — общий LIMIT на весь join обрезал
  связи у последних строк страницы; ORDER BY p.id — порядок связей у
  каждого родителя детерминирован;
- build_search_relation: дети O2M — ORDER BY id ASC, id родителей — одним
  параметром-массивом (= ANY), а не IN (%s, %s, ...).

No database.
"""

import pytest

from dotorm.fields import Char, Integer, Many2many, Many2one, One2many
from dotorm.model import DotModel

pytestmark = pytest.mark.unit


class Tag(DotModel):
    __table__ = "t_m2m_tag"

    id: int = Integer(primary_key=True)
    name: str | None = Char()


class Comment(DotModel):
    __table__ = "t_m2m_comment"

    id: int = Integer(primary_key=True)
    post_id: "Post | None" = Many2one(relation_table=lambda: Post)
    body: str | None = Char()


class Post(DotModel):
    __table__ = "t_m2m_post"

    id: int = Integer(primary_key=True)
    title: str | None = Char()
    tag_ids: list[Tag] = Many2many(
        relation_table=Tag,
        many2many_table="t_m2m_post_tag",
        column1="tag_id",
        column2="post_id",
    )
    comment_ids: list[Comment] = One2many(
        relation_table=Comment, relation_table_field="post_id"
    )


def _m2m(**kwargs):
    """build_get_many2many для Post.tag_ids владельца id=1."""
    field = Post.tag_ids
    kwargs.setdefault("fields", ["id", "name"])
    return Post._builder.build_get_many2many(
        1, Tag, field.many2many_table, field.column1, field.column2, **kwargs
    )


def _m2m_multiple(ids, **kwargs):
    """build_get_many2many_multiple для Post.tag_ids списка владельцев."""
    field = Post.tag_ids
    kwargs.setdefault("fields", ["id", "name"])
    return Post._builder.build_get_many2many_multiple(
        ids=ids,
        relation_table=Tag,
        many2many_table=field.many2many_table,
        column1=field.column1,
        column2=field.column2,
        **kwargs,
    )


class TestBuildGetMany2many:
    def test_no_limit_by_default(self):
        stmt, values = _m2m()

        assert "LIMIT" not in stmt
        assert values == (1,)

    def test_explicit_limit(self):
        stmt, values = _m2m(limit=5)

        assert stmt.endswith("LIMIT %s")
        assert values == (1, 5)

    def test_page_start_end(self):
        stmt, values = _m2m(start=2, end=6)

        assert stmt.endswith("LIMIT %s OFFSET %s")
        assert values == (1, 4, 2)  # (id, end - start, start)

    def test_order_by_is_qualified(self):
        stmt, _ = _m2m(fields=["name"], sort="id")
        assert "ORDER BY p.id desc" in stmt

        stmt, _ = _m2m(sort="name", order="asc")
        assert "ORDER BY p.name asc" in stmt

    def test_unknown_sort_falls_back_to_id(self):
        stmt, _ = _m2m(sort="(SELECT pg_sleep(5))")

        assert "pg_sleep" not in stmt
        assert "ORDER BY p.id" in stmt

    def test_filter_narrows_related_rows(self):
        stmt, values = _m2m(filter=[("name", "=", "x")])

        assert 'p.id IN (SELECT id FROM t_m2m_tag WHERE "name" = %s)' in stmt
        assert values == (1, "x")


class TestBuildGetMany2manyMultiple:
    def test_no_limit_and_ordered(self):
        stmt, values = _m2m_multiple([1, 2, 3])

        assert "LIMIT" not in stmt
        assert "ORDER BY p.id" in stmt
        assert "WHERE t.id IN (%s, %s, %s)" in stmt
        assert "pt.post_id as m2m_id" in stmt
        assert values == (1, 2, 3)

    def test_filter_values_follow_ids(self):
        stmt, values = _m2m_multiple([1, 2], filter=[("name", "=", "x")])

        assert 'p.id IN (SELECT id FROM t_m2m_tag WHERE "name" = %s)' in stmt
        assert values == (1, 2, "x")


class TestBuildSearchRelation:
    def _requests(self):
        records = [Post(id=1), Post(id=2)]
        requests = Post._builder.build_search_relation(
            [("comment_ids", Post.comment_ids), ("tag_ids", Post.tag_ids)],
            records,
        )
        return {req.field_name: req for req in requests}

    def test_o2m_children_ordered_by_id_with_array_param(self):
        req = self._requests()["comment_ids"]

        assert '"post_id" = ANY(%s)' in req.stmt
        assert req.stmt.rstrip().endswith("ORDER BY id ASC")
        assert req.value == ([1, 2],)

    def test_m2m_batch_without_limit(self):
        req = self._requests()["tag_ids"]

        assert "LIMIT" not in req.stmt
        assert "ORDER BY p.id" in req.stmt
        assert req.value == (1, 2)

    def test_no_records_no_requests(self):
        requests = Post._builder.build_search_relation(
            [("tag_ids", Post.tag_ids)], []
        )

        assert requests == []
