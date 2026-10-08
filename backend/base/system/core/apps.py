import logging
from typing import Tuple

from .app import App
from .service import Service

log = logging.getLogger(__name__)


class AppsCore:
    """Реестр приложений: имена, порядок, зависимости.

    Чистые вычисления над `info` приложений, без БД. Какие приложения
    активны — Environment.installed; граф установки и удаления — модуль
    apps_install (graph.py).
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

    # ── Зависимости ──────────────────────────────────────────────────

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
