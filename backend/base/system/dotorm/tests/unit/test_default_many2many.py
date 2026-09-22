"""
Дефолты по default_orm (model.py: _cache_default_plan) и связи при
создании: create → update после INSERT, списки записей у x2m равносильны
командам (relations.py: _update_relations).

No database.
"""

from typing import Any

import pytest

from dotorm.fields import Char, Integer, Many2many, Many2one, One2many
from dotorm.model import DotModel

pytestmark = pytest.mark.unit


class Tag(DotModel):
    __table__ = "t_m2m_default_tag"

    id: int = Integer(primary_key=True)
    name: str | None = Char()


class Comment(DotModel):
    __table__ = "t_m2m_default_comment"

    id: int = Integer(primary_key=True)
    text: str | None = Char()
    post_id: "Post | None" = Many2one(lambda: Post)


async def _default_tags():
    return [Tag(id=10), Tag(id=20)]


class Post(DotModel):
    __table__ = "t_m2m_default_post"

    id: int = Integer(primary_key=True)
    title: str | None = Char(default="untitled")
    # default только для формы: в INSERT не идёт
    hidden: str | None = Char(default="x", default_orm=False)
    author_id: "Tag | None" = Many2one(lambda: Tag)
    tag_ids: list["Tag"] = Many2many(
        lambda: Tag,
        "t_m2m_default_link",
        "tag_id",
        "post_id",
        store=False,
        default=_default_tags,
    )
    comment_ids: list["Comment"] = One2many(
        lambda: Comment, "post_id", store=False
    )


# Поля-связи объявлены списками записей; команды формы и голые id — это
# контракт API/кода, а не тип поля, отсюда Any.
def commands(**kwargs: list) -> Any:
    return kwargs


def refs(*items: Any) -> Any:
    return list(items)


class TestDefaults:
    def test_plan_filtered_by_default_orm_not_store(self):
        names = [name for name, _, _ in Post._cache_default_plan]
        assert names == ["title", "tag_ids"]

    async def test_apply_defaults(self):
        post = Post()
        await Post._apply_defaults(post)
        assert post.title == "untitled"
        assert post.is_assigned("hidden") is False
        assert [tag.id for tag in post.tag_ids] == [10, 20]

    async def test_form_sees_form_only_default(self):
        values = await Post.get_default_values({})
        assert values["hidden"] == "x"

    def test_assigned_relations_skip_many2one_and_empty(self):
        post = Post(
            author_id=Tag(id=1), tag_ids=[Tag(id=10)], comment_ids=commands()
        )
        assert Post._assigned_relations(post) == ["tag_ids"]


@pytest.fixture
def calls(monkeypatch):
    """Двойники записи связей: (link-пары, созданные дети)."""
    linked: list = []
    created: list = []

    async def link(_owner, field, values, session=None):
        linked.append(values)

    async def create_bulk(records, **kwargs):
        created.extend(records)
        return [{"id": 100}]

    monkeypatch.setattr(Post, "link_many2many", link)
    monkeypatch.setattr(
        Post, "_get_db_session", classmethod(lambda cls, session=None: None)
    )
    monkeypatch.setattr(Comment, "create_bulk", create_bulk)
    monkeypatch.setattr(Tag, "create_bulk", create_bulk)
    return linked, created


class TestListsAsCommands:
    async def test_many2many_records_and_ids_are_selected(self, calls):
        linked, _ = calls
        await Post(id=7)._update_relations(
            Post(tag_ids=refs(Tag(id=10), 20)), ["tag_ids"]
        )
        assert linked == [[(7, 10), (7, 20)]]

    async def test_new_record_is_created_then_linked(self, calls):
        linked, created = calls
        await Post(id=7)._update_relations(
            Post(tag_ids=[Tag(name="new")]), ["tag_ids"]
        )
        assert created[0].name == "new"
        assert linked == [[(7, 100)]]

    async def test_new_child_gets_parent(self, calls):
        _, created = calls
        await Post(id=7)._update_relations(
            Post(comment_ids=[Comment(text="hi")]), ["comment_ids"]
        )
        assert (created[0].text, created[0].post_id) == ("hi", 7)

    async def test_many_owners_one_query_per_field(self, calls):
        """update_bulk: одни команды на несколько записей."""
        linked, created = calls
        form_row = {"text": "f", "post_id": "VirtualId"}
        payload = Post(
            tag_ids=[Tag(id=10)], comment_ids=commands(created=[form_row])
        )
        await payload._update_relations(
            payload, ["tag_ids", "comment_ids"], ids=[7, 8]
        )
        assert linked == [[(7, 10), (8, 10)]]
        assert [(c.text, c.post_id) for c in created] == [("f", 7), ("f", 8)]
        assert form_row["post_id"] == "VirtualId"  # словарь формы не тронут
