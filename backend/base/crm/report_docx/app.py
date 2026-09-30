# Copyright 2025 FARA CRM
# Report DOCX module — application

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL


class ReportDocxApp(App):
    """
    Модуль генерации отчётов из DOCX-шаблонов.

    - Хранение DOCX-шаблонов с Jinja2-тегами (через Attachment)
    - Рендеринг через docxtpl (+ фильтры money/date/datetime), content
      controls конструктора разворачиваются перед рендером
    - PDF: LibreOffice, если установлен, иначе встроенная простая конверсия
    - Отправка по расписанию: методы cron_send_report_* на report_template
    - Сидер шаблонов-образцов (seed.py) — сами образцы, функции данных и
      примеры задач живут в модулях предметных областей (sales_report_docx)

    Конструктор шаблонов (каталог полей, превью) — отдельный модуль
    report_docx_design.
    """

    info = {
        "name": "Report DOCX",
        "summary": "DOCX template report generation with PDF conversion",
        "author": "FARA CRM",
        "category": "Reporting",
        "version": "1.2.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["security"],
        "post_init": True,
    }

    # Шаблоны видят все (кнопка «Печать» читает список), правят — только
    # администраторы: конструктор и загрузка DOCX — технические настройки.
    BASE_USER_ACL = {
        "report_template": ACL.READ_ONLY,
    }

    ROLE_ACL = {
        "system_admin": {
            "report_template": ACL.FULL,
        },
    }
