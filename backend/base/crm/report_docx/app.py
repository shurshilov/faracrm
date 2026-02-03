# Copyright 2025 FARA CRM
# Report DOCX module — application

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL


class ReportDocxApp(App):
    """
    Модуль генерации отчётов из DOCX-шаблонов.

    - Хранение DOCX-шаблонов с Jinja2-тегами (через Attachment)
    - Рендеринг через docxtpl
    - PDF-конверсия через LibreOffice
    """

    info = {
        "name": "Report DOCX",
        "summary": "DOCX template report generation with PDF conversion",
        "author": "FARA CRM",
        "category": "Reporting",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "report_template": ACL.FULL,
    }
