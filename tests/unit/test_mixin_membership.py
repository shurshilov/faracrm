# Copyright 2025 FARA CRM
# Unit tests for MemberMixin — чистая логика, без БД.

from types import SimpleNamespace

import pytest

from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.dotorm.dotorm.access import (
    get_access_session,
    set_access_session,
)
from backend.base.system.membership.mixin import MemberMixin
from backend.base.system.membership.permissions import MemberPermissions

WRITE = MemberPermissions(can_write=True)
INVITE = MemberPermissions(can_invite=True)


class _FakeMember(MemberMixin):
    """Минимальная имитация мембера — только поля, без ORM."""

    _member_res_field = "chat_id"
    _member_res_model = staticmethod(lambda: None)

    def __init__(self, is_admin: bool = False, **perms: bool):
        self.is_admin = is_admin
        self.can_read = perms.get("can_read", False)
        self.can_write = perms.get("can_write", False)
        self.can_invite = perms.get("can_invite", False)
        self.can_remove = perms.get("can_remove", False)


@pytest.fixture
def session():
    """Сессия запроса: по ней check_permissions узнаёт системного админа."""
    previous = get_access_session()
    session = SimpleNamespace(is_system_admin=False)
    set_access_session(session)
    yield session
    set_access_session(previous)


def _denied(member, permission=None) -> str:
    """Код отказа check_permissions."""
    with pytest.raises(FaraException) as error:
        _FakeMember.check_permissions(member, permission)
    return error.value.args[0]["content"]


class TestCheckPermissions:
    """Единая проверка: системный админ, админ контейнера, права участника.
    Участника передают уже найденным (None — не участник), нужные права —
    набором MemberPermissions."""

    def test_system_admin_passes_without_membership(self, session):
        session.is_system_admin = True
        _FakeMember.check_permissions(None)
        _FakeMember.check_permissions(_FakeMember(), WRITE)

    def test_non_member_denied(self, session):
        assert _denied(None) == "PERMISSION_DENIED"
        assert _denied(None, WRITE) == "PERMISSION_DENIED"

    def test_admin_passes(self, session):
        admin = _FakeMember(is_admin=True)
        _FakeMember.check_permissions(admin)
        _FakeMember.check_permissions(admin, WRITE)

    def test_member_passes_with_required_permission(self, session):
        _FakeMember.check_permissions(_FakeMember(can_write=True), WRITE)

    def test_member_denied_without_required_permission(self, session):
        member = _FakeMember(can_write=True)
        assert _denied(member, INVITE) == "PERMISSION_DENIED"
        # Без набора прав проходят только админы
        assert _denied(member) == "PERMISSION_DENIED"

    def test_every_permission_of_the_set_is_required(self, session):
        both = MemberPermissions(can_write=True, can_invite=True)
        assert (
            _denied(_FakeMember(can_write=True), both) == "PERMISSION_DENIED"
        )
        _FakeMember.check_permissions(
            _FakeMember(can_write=True, can_invite=True), both
        )

    def test_empty_set_requires_nothing_but_membership(self, session):
        """В пустом наборе прав нет — участнику их и не нужно."""
        assert MemberPermissions() == MemberPermissions(
            can_read=False,
            can_write=False,
            can_invite=False,
            can_remove=False,
            is_admin=False,
        )
        _FakeMember.check_permissions(_FakeMember(), MemberPermissions())


# class TestAssertConfigured:
#     def test_raises_if_member_res_field_missing(self):
#         class BadMember(MemberMixin):
#             # забыли _member_res_field / _member_res_model
#             pass

#         # напрямую атрибуты затираем, чтобы сымитировать "не задано"
#         BadMember._member_res_field = None  # type: ignore[assignment]
#         BadMember._member_res_model = None  # type: ignore[assignment]

#         with pytest.raises(RuntimeError, match="_member_res_field"):
#             BadMember._assert_configured()

#     def test_passes_if_configured(self):
#         class GoodMember(MemberMixin):
#             _member_res_field = "chat_id"
#             _member_res_model = staticmethod(lambda: None)

#         # не должно упасть
#         GoodMember._assert_configured()
