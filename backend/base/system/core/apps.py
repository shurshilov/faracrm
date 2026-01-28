from typing import Tuple
from .service import Service
from .app import App


class AppsCore:
    "Структура для работы с приложениями"

    def get_names(self) -> list[str]:
        apps: list[Tuple[str, App]] = [
            (app_name, getattr(self, app_name))
            for app_name in dir(self)
            if not app_name.startswith("_") and not callable(getattr(self, app_name))
        ]
        apps_sorted = sorted(apps, key=lambda x: x[1].info.get("sequence", 10))
        apps_names_sorted = [app_tuple[0] for app_tuple in apps_sorted]
        return apps_names_sorted

    def get_list(self):

        apps: list[App | Service] = []
        for app_name in self.get_names():
            app = getattr(self, app_name)
            # if isinstance(app, App):
            apps.append(app)
        return apps
