"""
Граф установки приложений: что ставить вместе с приложением, что удалять
вместе с ним и что удалять нельзя. Чистые вычисления над info приложений
реестра (AppsCore), без БД.
"""

from typing import Iterable

from backend.base.system.core.apps import AppsCore
from backend.base.system.core.exceptions import environment


def is_core(apps: AppsCore, code: str) -> bool:
    """Нельзя удалить: core в info. Сервис (инфраструктура) — core по
    умолчанию; с "core": False он отключаемый — запущен, только пока
    установлен (AppsInstallService.sync_services)."""
    app = apps.get(code)
    return bool(app and app.info.get("core", app.info.get("service")))


def _ensure_known(apps: AppsCore, code: str) -> None:
    if apps.get(code) is None:
        raise environment.FaraException(
            {
                "content": "#APP_NOT_FOUND",
                "detail": code,
                "status_code": 404,
            }
        )


def install_order(
    apps: AppsCore, targets: Iterable[str], installed: Iterable[str]
) -> list[str]:
    """Что установить ради targets: сами приложения и ещё не
    установленные зависимости, зависимости — раньше зависимых."""
    installed = set(installed)
    order: list[str] = []

    def visit(code: str, stack: tuple[str, ...]) -> None:
        if code in installed or code in order:
            return
        if code in stack:
            raise ValueError(f"Cycle in app depends: {stack + (code,)}")
        for dep in apps.depends_of(code):
            visit(dep, stack + (code,))
        order.append(code)

    for code in targets:
        _ensure_known(apps, code)
        visit(code, ())
    return order


def uninstall_order(
    apps: AppsCore, targets: Iterable[str], installed: Iterable[str]
) -> list[str]:
    """Что удалить вместе с targets: все установленные зависимые
    (транзитивно), зависимые — первыми. Core в списке — #APP_IS_CORE."""
    installed = set(installed)
    order: list[str] = []

    def visit(code: str) -> None:
        if code in order or code not in installed:
            return
        for dependent in sorted(installed):
            if code in apps.depends_of(dependent):
                visit(dependent)
        order.append(code)

    for code in targets:
        _ensure_known(apps, code)
        visit(code)

    core = [c for c in order if is_core(apps, c)]
    if core:
        raise environment.FaraException(
            {
                "content": "#APP_IS_CORE",
                "detail": ", ".join(core),
                "status_code": 400,
            }
        )
    return order
