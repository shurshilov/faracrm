from backend.base.system.core.app import App


class AdministrationApp(App):
    """
    Приложение добавляет ручки общей информации
    """

    info = {
        "name": "App administration",
        "summary": "administration",
        "author": "Artem Shurshilov",
        "category": "Base",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": [],
    }
