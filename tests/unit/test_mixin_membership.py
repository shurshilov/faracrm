# Copyright 2025 FARA CRM
# Unit tests for MemberMixin — чистая логика, без БД.


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


class TestHasPermission:
    def test_returns_true_for_granted_permission(self):
        m = _FakeMember(can_write=True)
        assert m.has_permission("can_write") is True

    def test_returns_false_for_denied_permission(self):
        m = _FakeMember(can_write=False)
        assert m.has_permission("can_write") is False

    def test_returns_false_for_unknown_permission(self):
        # Поля can_unknown нет — не падаем, просто False.
        m = _FakeMember(can_write=True)
        assert m.has_permission("can_unknown") is False

    def test_admin_overrides_all_permissions(self):
        m = _FakeMember(is_admin=True, can_write=False, can_pin=False)
        assert m.has_permission("can_write") is True
        assert m.has_permission("can_pin") is True
        # Даже несуществующее — админу разрешено.
        assert m.has_permission("can_anything") is True

    def test_is_admin_itself_as_permission(self):
        m = _FakeMember(is_admin=False)
        assert m.has_permission("is_admin") is False

        admin = _FakeMember(is_admin=True)
        assert admin.has_permission("is_admin") is True


class TestGetPermissions:
    def test_returns_all_can_fields(self):
        m = _FakeMember(can_read=True, can_write=False, can_pin=True)
        result = m.get_permissions()

        assert result["can_read"] is True
        assert result["can_write"] is False
        assert result["can_pin"] is True
        assert result["is_admin"] is False

    def test_admin_sets_all_can_true(self):
        m = _FakeMember(
            is_admin=True,
            can_read=False,
            can_write=False,
            can_pin=False,
        )
        result = m.get_permissions()

        assert result["is_admin"] is True
        assert result["can_read"] is True
        assert result["can_write"] is True
        assert result["can_pin"] is True

    def test_ignores_non_bool_can_attributes(self):
        """Атрибут can_xxx, не являющийся bool, игнорируется."""
        m = _FakeMember(can_read=True)
        m.can_whatever = "some string"  # type: ignore[attr-defined]

        result = m.get_permissions()
        assert "can_whatever" not in result
        assert result["can_read"] is True


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
