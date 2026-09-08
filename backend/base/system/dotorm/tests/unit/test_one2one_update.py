"""
Unit-тесты записи One2one через update (orm/mixins/relations.py,
_update_relations).

Контракт с API, на который опирается kdpnm (Message.message_attributes_id):
- связь приходит словарём полей связанной записи, как created у One2many,
  и перед записью превращается в запись relation_table;
- связанная строка ищется по обратному полю (relation_table_field = id
  родителя) и обновляется этой записью; готовая запись проходит как есть;
- если связанной строки нет — ничего не пишется и ничего не падает.

No database, no network. Pure function tests.
"""

import pytest

from dotorm.fields import Char, Integer, One2one
from dotorm.model import DotModel

pytestmark = pytest.mark.unit


class Profile(DotModel):
    __table__ = "t_one2one_profile"

    id: int = Integer(primary_key=True)
    account_id: int | None = Integer()
    bio: str | None = Char()


class Account(DotModel):
    __table__ = "t_one2one_account"

    id: int = Integer(primary_key=True)
    name: str | None = Char()
    profile_id: "Profile | None" = One2one(
        store=False, relation_table=Profile, relation_table_field="account_id"
    )


class RelatedRow:
    """Двойник найденной связанной строки: запоминает payload своего update."""

    def __init__(self):
        self.payloads = []

    async def update(self, payload, *args, **kwargs):
        self.payloads.append(payload)


@pytest.fixture
def related(monkeypatch):
    """Profile.search находит одну строку; сессия БД не нужна."""
    row = RelatedRow()
    row.search_calls = []

    async def fake_search(**kwargs):
        row.search_calls.append(kwargs)
        return [row]

    monkeypatch.setattr(Profile, "search", fake_search)
    monkeypatch.setattr(
        Account, "_get_db_session", classmethod(lambda cls, session=None: None)
    )
    return row


class TestOne2oneUpdate:
    async def test_dict_from_api_becomes_related_record(self, related):
        await Account(id=7)._update_relations(
            Account(profile_id={"bio": "hi"}), ["profile_id"]
        )

        (payload,) = related.payloads
        assert isinstance(payload, Profile)
        assert payload.bio == "hi"

    async def test_related_row_is_found_by_parent_id(self, related):
        await Account(id=7)._update_relations(
            Account(profile_id={"bio": "hi"}), ["profile_id"]
        )

        assert related.search_calls == [
            {"limit": 1, "fields": ["id"], "filter": [("account_id", "=", 7)]}
        ]

    async def test_ready_record_passes_through_unchanged(self, related):
        profile = Profile(bio="ready")

        await Account(id=7)._update_relations(
            Account(profile_id=profile), ["profile_id"]
        )

        assert related.payloads == [profile]

    async def test_missing_related_row_writes_nothing(
        self, monkeypatch, related
    ):
        async def nothing(**kwargs):
            return []

        monkeypatch.setattr(Profile, "search", nothing)

        await Account(id=7)._update_relations(
            Account(profile_id={"bio": "hi"}), ["profile_id"]
        )

        assert related.payloads == []
