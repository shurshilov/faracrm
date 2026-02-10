from typing import Tuple

from .app import App
from .service import Service


class AppsCore:
    """Структура для работы с приложениями."""

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
