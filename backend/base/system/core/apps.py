import logging
from typing import Iterable, Tuple

from .app import App
from .exceptions import environment
from .service import Service

log = logging.getLogger(__name__)


class AppsCore:
    """Реестр приложений: имена, порядок, граф зависимостей.

    Чистые вычисления над `info` приложений, без БД. Состояние
    «установлено» живёт в Environment.installed и в таблице apps.
    """

    def get_names(self) -> list[str]:
        """Получить отсортированные имена приложений."""
        apps: list[Tuple[str, App]] = [
            (app_name, getattr(self, app_name))
            for app_name in dir(self)
            if not app_name.startswith("_")
            and not callable(getattr(self, app_name))
        ]
        apps_sorted = sorted(apps, key=lambda x: x[1].info.get("sequence", 10))
        return [app_tuple[0] for app_tuple in apps_sorted]

    def get_list(self) -> list[App | Service]:
        """Получить список всех приложений."""
        return [getattr(self, app_name) for app_name in self.get_names()]

    def get(self, code: str) -> App | Service | None:
        """Приложение по коду (имени атрибута) или None."""
        if not code or code.startswith("_"):
            return None
        app = getattr(self, code, None)
        return None if app is None or callable(app) else app

    # ── Граф зависимостей ────────────────────────────────────────────

    def depends_of(self, code: str) -> list[str]:
        """Объявленные зависимости — только известные коды. Опечатка в
        depends не должна молча блокировать установку: логируем и пропускаем.
        """
        app = self.get(code)
        result: list[str] = []
        for dep in (app.info.get("depends") or []) if app else []:
            if self.get(dep) is None:
                log.warning("App %r depends on unknown app %r", code, dep)
                continue
            result.append(dep)
        return result

    def is_core(self, code: str) -> bool:
        """Нельзя удалить: сервис (инфраструктура) или core в info."""
        app = self.get(code)
        return bool(app and (app.info.get("service") or app.info.get("core")))

    def _ensure_known(self, code: str) -> None:
        if self.get(code) is None:
            raise environment.FaraException(
                {
                    "content": "#APP_NOT_FOUND",
                    "detail": code,
                    "status_code": 404,
                }
            )

    def install_order(
        self, targets: Iterable[str], installed: Iterable[str]
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
            for dep in self.depends_of(code):
                visit(dep, stack + (code,))
            order.append(code)

        for code in targets:
            self._ensure_known(code)
            visit(code, ())
        return order

    def uninstall_order(
        self, targets: Iterable[str], installed: Iterable[str]
    ) -> list[str]:
        """Что удалить вместе с targets: все установленные зависимые
        (транзитивно), зависимые — первыми. Core в списке — #APP_IS_CORE."""
        installed = set(installed)
        order: list[str] = []

        def visit(code: str) -> None:
            if code in order or code not in installed:
                return
            for dependent in sorted(installed):
                if code in self.depends_of(dependent):
                    visit(dependent)
            order.append(code)

        for code in targets:
            self._ensure_known(code)
            visit(code)

        core = [c for c in order if self.is_core(c)]
        if core:
            raise environment.FaraException(
                {
                    "content": "#APP_IS_CORE",
                    "detail": ", ".join(core),
                    "status_code": 400,
                }
            )
        return order
