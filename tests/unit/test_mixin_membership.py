# Copyright 2025 FARA CRM
# Unit tests for MemberMixin — чистая логика, без БД.

import pytest

from backend.base.system.core.exceptions.environment import FaraException
from backend.base.system.membership.mixin import MemberMixin


class _FakeMember(MemberMixin):
    """Минимальная имитация мембера — только поля, без ORM."""

    _member_res_field = "chat_id"
    _member_res_model = staticmethod(lambda: None)

    def __init__(
        self,
        is_admin: bool = False,
        **perms: bool,
    ):
        self.is_admin = is_admin
        # Стандартные права чата для тестов
        self.can_read = perms.get("can_read", False)
        self.can_write = perms.get("can_write", False)
        self.can_pin = perms.get("can_pin", False)


class TestRequire:
    def test_passes_with_permission(self):
        m = _FakeMember(can_write=True)
        m.require(m.can_write)

    def test_denied_without_permission(self):
        m = _FakeMember(can_write=False)
        with pytest.raises(FaraException) as error:
            m.require(m.can_write)
        assert error.value.args[0]["content"] == "PERMISSION_DENIED"

    def test_admin_passes_without_permission(self):
        m = _FakeMember(is_admin=True, can_write=False, can_pin=False)
        m.require(m.can_write)
        m.require(m.can_pin)


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
