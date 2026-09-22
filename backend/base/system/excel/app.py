"""Excel application."""

from backend.base.system.core.app import App


class ExcelApp(App):
    """
    Экспорт и импорт записей через Excel (.xlsx) для любой модели автокруда.

    Экспорт читает выборку списка через Model.search (ACL и правила строк —
    штатные), импорт создаёт записи через Model.create. Своих моделей и
    настроек нет; фронт показывает кнопки, пока приложение установлено.
    """

    info = {
        "name": "Excel",
        "summary": "Export list selection to .xlsx, import records from .xlsx",
        "author": "FARA ERP",
        "category": "System",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["security"],
    }
