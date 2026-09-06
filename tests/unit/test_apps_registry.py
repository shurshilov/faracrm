"""
Реестр приложений (AppsCore): порядок установки и удаления, защита core.
Чистые вычисления над info — без БД.

Run: pytest tests/unit/test_apps_registry.py -v -m unit
"""

import pytest

from backend.base.system.core.apps import AppsCore
from backend.base.system.core.exceptions.environment import FaraException

pytestmark = pytest.mark.unit


def _app(**info):
    """Фейковое приложение: только info."""
    return type("FakeApp", (), {"info": info})()


@pytest.fixture
def apps() -> AppsCore:
    # security ─┬─ users ─┬─ leads ─── chat(service)
    #           │         └─ market ─── market_email
    #           └─ files (core)
    registry = AppsCore()
    for code, app in {
        "security": _app(service=True, sequence=1),
        "users": _app(depends=["security"], core=True),
        "files": _app(core=True),
        "leads": _app(depends=["users"]),
        "chat": _app(service=True, depends=["leads"]),
        "market": _app(depends=["users", "typo_unknown"]),
        "market_email": _app(depends=["market"]),
    }.items():
        setattr(registry, code, app)
    return registry


class TestInstallOrder:
    def test_pulls_missing_depends_first(self, apps):
        order = apps.install_order(
            ["market_email"], installed={"security", "users", "files"}
        )
        assert order == ["market", "market_email"]

    def test_already_installed_are_skipped(self, apps):
        assert apps.install_order(["leads"], installed={"leads"}) == []

    def test_unknown_app(self, apps):
        with pytest.raises(FaraException) as exc:
            apps.install_order(["nope"], installed=set())
        assert exc.value.args[0]["content"] == "#APP_NOT_FOUND"

    def test_unknown_depend_is_ignored(self, apps):
        # typo_unknown в depends маркетплейса — предупреждение, не отказ.
        assert apps.depends_of("market") == ["users"]


class TestUninstallOrder:
    def test_dependents_go_first(self, apps):
        installed = {"security", "users", "files", "market", "market_email"}
        assert apps.uninstall_order(["market"], installed) == [
            "market_email",
            "market",
        ]

    def test_core_is_protected(self, apps):
        with pytest.raises(FaraException) as exc:
            apps.uninstall_order(["users"], installed={"security", "users"})
        assert exc.value.args[0]["content"] == "#APP_IS_CORE"

    def test_service_dependent_blocks_uninstall(self, apps):
        # chat (service) зависит от leads → leads удалить нельзя.
        installed = {"security", "users", "leads", "chat"}
        with pytest.raises(FaraException) as exc:
            apps.uninstall_order(["leads"], installed)
        assert "chat" in exc.value.args[0]["detail"]

    def test_not_installed_is_noop(self, apps):
        assert apps.uninstall_order(["market"], installed={"users"}) == []

    def test_core_flag(self, apps):
        assert apps.is_core("security") and apps.is_core("files")
        assert not apps.is_core("leads")
