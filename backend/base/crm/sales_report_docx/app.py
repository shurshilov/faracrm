# Copyright 2025 FARA CRM
# Sales Report DOCX module — application

import json
from pathlib import Path
from typing import TYPE_CHECKING

from backend.base.crm.report_docx.seed import seed_report_templates
from backend.base.system.core.app import App

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

TEMPLATES_DIR = Path(__file__).parent / "templates"
PERIOD_TEMPLATE_NAME = "Отчёт по продажам за период"


def _contract_sample(name: str, file: str) -> dict:
    return {
        "name": name,
        "description": "Образец документа по договору, теги — ключи contract_data",
        "model_name": "contract",
        "python_function": "contract_data",
        "report_type": "record",
        "output_format": "pdf",
        "file": TEMPLATES_DIR / file,
    }


# Шаблоны-образцы с файлами — сеются при старте (см. report_docx/seed.py),
# дальше их правят в конструкторе.
SAMPLE_TEMPLATES = [
    {
        "name": "Счёт на оплату",
        "description": "Образец: счёт по заказу, теги — ключи sale_invoice_rus",
        "model_name": "sales",
        "python_function": "sale_invoice_rus",
        "report_type": "record",
        "output_format": "pdf",
        "file": TEMPLATES_DIR / "Счет на оплату 2018.docx",
    },
    {
        "name": PERIOD_TEMPLATE_NAME,
        "description": "Образец сводного отчёта: продажи за N дней "
        "(sales_period_data, параметр days)",
        "model_name": "sales",
        "python_function": "sales_period_data",
        "report_type": "summary",
        "output_format": "pdf",
        "file": TEMPLATES_DIR / "Отчёт по продажам за период.docx",
    },
    _contract_sample("Договор с клиентом", "Договор с клиентом.docx"),
    _contract_sample("Договор с поставщиком", "Договор с поставщиком.docx"),
    _contract_sample("Договор-счёт", "Договор счет.docx"),
    _contract_sample(
        "Дополнительное соглашение", "Дополнительное соглашение.docx"
    ),
    _contract_sample(
        "Уведомление об уполномоченных лицах",
        "Уведомление об уполномоченных лицах.docx",
    ),
]

# Примеры рассылки отчёта по расписанию: (название, метод report_template,
# kwargs задачи без template_id — его даёт сидер шаблонов). Создаются
# ВЫКЛЮЧЕННЫМИ — админ правит kwargs и включает. Код «собрать и отправить» —
# в методах модели (см. ReportTemplate); params уходят в функцию данных.
EXAMPLE_CRON_JOBS = [
    (
        "Отправка еженедельных отчётов: пример (email)",
        "cron_send_report_email",
        {
            "to": "manager@example.com",
            "subject": "Продажи за неделю",
            "params": {"days": 7},
        },
    ),
    (
        "Отправка еженедельных отчётов: пример (Telegram)",
        "cron_send_report_telegram",
        {"chat_id": "123456789", "params": {"days": 7}},
    ),
]


class SalesReportDocxApp(App):
    """
    Печатные формы и отчёты по продажам для модуля report_docx.

    - Функции данных на Sale (models/sale_ext.py): счёт на оплату по заказу
      (sale_invoice_rus), продажи за период (sales_period_data); на Contract
      (models/contract_ext.py): документы по договору (contract_data)
    - Шаблоны-образцы с файлами из templates/ — сеются при старте
      (SAMPLE_TEMPLATES): счёт, отчёт за период, пять документов по договору
    - Примеры cron-задач рассылки отчёта (email, Telegram) — выключены
    """

    info = {
        "name": "Sales Report DOCX",
        "summary": "Sales documents and reports for DOCX templates",
        "author": "FARA CRM",
        "category": "Sales",
        "version": "1.1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["sales", "contract", "report_docx", "cron"],
        "post_init": True,
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        template_ids = await seed_report_templates(env, SAMPLE_TEMPLATES)
        period_template_id = template_ids.get(PERIOD_TEMPLATE_NAME, 1)

        for name, method_name, kwargs in EXAMPLE_CRON_JOBS:
            await env.models.cron_job.create_or_update(
                env=env,
                name=name,
                model_name="report_template",
                method_name=method_name,
                kwargs=json.dumps(
                    {"template_id": period_template_id, **kwargs},
                    ensure_ascii=False,
                ),
                interval_number=1,
                interval_type="weeks",
                active=False,
                priority=30,
            )
