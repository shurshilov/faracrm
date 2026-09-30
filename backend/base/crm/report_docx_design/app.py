# Copyright 2025 FARA CRM
# Report DOCX Designer module — application

from backend.base.system.core.app import App


class ReportDocxDesignApp(App):
    """
    Конструктор шаблонов отчётов (страница /report_template/{id}/design).

    - Каталог полей шаблона: поля записи модели + ключи функции данных,
      объявленные @report_fields (GET /reports/templates/{id}/fields)
    - Превью: рендер несохранённого DOCX из редактора с данными записи
      (POST /reports/preview)

    Сам движок (шаблоны, рендер, PDF, рассылка) — в report_docx; конструктор
    можно удалить, шаблоны и печать продолжат работать. Права те же, что у
    report_template: править шаблоны могут администраторы.
    """

    info = {
        "name": "Report DOCX Designer",
        "summary": "Template designer: field catalog and live preview",
        "author": "FARA CRM",
        "category": "Reporting",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["report_docx"],
    }
