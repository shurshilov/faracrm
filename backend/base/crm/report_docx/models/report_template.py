import asyncio
import inspect
import json
import logging
from datetime import datetime, timezone
from typing import Any

from backend.base.crm.attachments.models.attachments import Attachment
from backend.base.system.core.enviroment import env
from backend.base.system.dotorm.dotorm.exceptions import RecordNotFound
from backend.base.system.dotorm.dotorm.fields import (
    Binary,
    Boolean,
    Char,
    Integer,
    Many2many,
    Many2one,
    One2many,
    PolymorphicMany2one,
    Selection,
    Text,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.schemas.base_schema import Id
from ..utils.engine import DocxReportEngine

log = logging.getLogger(__name__)


class ReportTemplate(DotModel):
    """
    Шаблон отчёта DOCX.

    Хранит ссылку на Attachment с DOCX-файлом (Jinja2-теги).
    model_name — модель (имя таблицы), на которой лежат функции данных. Для
    документа по записи это и модель самой записи: на её форме появляется
    кнопка «Печать».
    Функции данных — @staticmethod (env, **params) -> dict на классе модели,
    помеченные @report_fields; ключи дикта = теги шаблона. Движок сам
    вызывает те, чьи ключи стоят в шаблоне (см. _build_context). Живут в
    модулях предметных областей, например sales_report_docx
    (Sale.sale_invoice_rus, Sale.sales_period_data).
    report_type — документ по записи (params = {"record_id": id}: в контекст
    попадают все поля записи, см. record_context, плюс дикты функций) или
    сводный отчёт (только дикты функций, params — их аргументы, например
    период; форма — data_params); сводные не показываются в меню «Печать»
    записи, их собирают кнопкой «Сформировать» на форме шаблона и cron.

    Конструктор шаблонов (каталог полей, превью) — модуль report_docx_design,
    он пользуется публичными помощниками get_template / resolve_model /
    data_functions / render_bytes.
    """

    __table__ = "report_template"

    id: Id = Integer(primary_key=True)
    name: str = Char(string="Report Name")
    active: bool = Boolean(default=True)

    model_name: str = Char(
        string="Model",
        help="DotORM table name, e.g. 'sales', 'partners'",
    )
    # python_function: str = Char(
    #     string="Data Function",
    #     help="Method name on model class, e.g. 'sale_invoice_rus'",
    # )
    report_type: str = Selection(
        options=[
            ("record", "Документ по записи"),
            ("summary", "Сводный отчёт"),
        ],
        default="record",
        # DDL DEFAULT: старые шаблоны — документы по записи без миграции
        default_db=True,
        string="Report Type",
    )
    template_file: Attachment | None = PolymorphicMany2one(
        relation_table=Attachment,
        string="DOCX Template",
    )
    output_format: str = Selection(
        options=[
            ("docx", "DOCX"),
            ("pdf", "PDF"),
        ],
        default="docx",
        string="Output Format",
    )
    description: str | None = Text(string="Description")

    # ------------------------------------------------------------------
    # Шаблон, модель, функция данных
    # ------------------------------------------------------------------

    @classmethod
    async def get_template(cls, template_id: int) -> "ReportTemplate":
        """Шаблон с полями настройки; RecordNotFound, если его нет."""
        tmpl = await cls.search_one(
            filter=[("id", "=", template_id)],
            fields=[
                "id",
                "name",
                "model_name",
                "report_type",
                "template_file",
                "output_format",
            ],
        )
        if not tmpl:
            raise RecordNotFound("report_template", template_id)
        return tmpl

    @staticmethod
    def resolve_model(model_name: str | None):
        """Модель по имени ТАБЛИЦЫ (как в /auto/{model} и у кнопки «Печать»):
        у partners/sales оно не совпадает с атрибутом Models (partner/sale),
        поэтому сначала таблица, затем атрибут — как _resolve_model в onchange.
        """
        model_cls = env.models._table_to_model_class.get(
            model_name or ""
        ) or getattr(env.models, model_name or "", None)
        if model_cls is None:
            raise ValueError(f"Model '{model_name}' not found")
        return model_cls

    @staticmethod
    def data_functions(model_cls, with_record: bool = True) -> list:
        """Функции данных модели — помеченные @report_fields. Без записи
        (with_record=False, сводный отчёт) — только те, что не ждут
        record_id. Ключ объявляет одна функция модели: иначе по тегу не
        понять, какую вызывать."""
        funcs, owners = [], {}
        for name in dir(model_cls):
            func = getattr(model_cls, name, None)
            keys = getattr(func, "_report_fields", None)
            if not callable(func) or keys is None:
                continue
            for key in keys:
                if key in owners:
                    raise ValueError(
                        f"Report key '{key}' is declared by both "
                        f"'{owners[key]}' and '{name}'"
                    )
                owners[key] = name
            takes_record = "record_id" in inspect.signature(func).parameters
            if with_record or not takes_record:
                funcs.append(func)
        return funcs

    @staticmethod
    def data_params(funcs: list) -> dict[str, dict]:
        """Аргументы функций данных для формы отчёта: имя → {name, type,
        default, label}. Тип — int/float/bool по аннотации, остальное str;
        подпись — из @report_params. env, record_id и **kwargs в форму не
        идут. Общий аргумент нескольких функций — одно поле: подпись и
        значение по умолчанию у первой функции."""
        result: dict[str, dict] = {}
        for func in funcs:
            labels = getattr(func, "_report_params", {})
            for name, param in inspect.signature(func).parameters.items():
                if name in ("env", "record_id") or param.kind in (
                    param.VAR_POSITIONAL,
                    param.VAR_KEYWORD,
                ):
                    continue
                # Аннотация — класс (int) или строка ("int")
                type_name = getattr(
                    param.annotation, "__name__", param.annotation
                )
                result.setdefault(
                    name,
                    {
                        "name": name,
                        "type": (
                            type_name
                            if type_name in ("int", "float", "bool")
                            else "str"
                        ),
                        "default": (
                            None
                            if param.default is param.empty
                            else param.default
                        ),
                        "label": labels.get(name, name),
                    },
                )
        return result

    @staticmethod
    def takes_kwargs(func) -> bool:
        """Функция принимает **kwargs — ей уходят все params."""
        params = inspect.signature(func).parameters.values()
        return any(p.kind is p.VAR_KEYWORD for p in params)

    # ------------------------------------------------------------------
    # Данные: запись → дикт + дикт функции
    # ------------------------------------------------------------------

    @staticmethod
    def _context_fields(model_cls) -> tuple[list[str], dict[str, dict]]:
        """Поля записи для контекста: все публичные, кроме байтов,
        полиморфных вложений и полей с ролевым доступом; связи — с публичными
        скалярами связанной модели (один уровень вглубь)."""
        names: list[str] = []
        nested: dict[str, dict] = {}
        for name, field in model_cls.get_public_fields().items():
            if isinstance(field, Binary) or field._role_acl:
                continue
            if isinstance(field, (Many2one, One2many, Many2many)):
                related = field.relation_table
                if related is None:
                    continue
                sub_names = [
                    sub
                    for sub, sub_field in related.get_public_fields().items()
                    if not sub_field.relation
                    and not isinstance(sub_field, Binary)
                    and not sub_field._role_acl
                ]
                nested[name] = {"fields": sub_names}
            elif field.relation:
                continue
            names.append(name)
        return names, nested

    @classmethod
    def _to_plain(cls, value: Any, depth: int) -> Any:
        """Запись/список записей → dict/list (скаляры как есть).

        depth — сколько уровней записей раскрыть в dict публичных полей;
        глубже запись сворачивается в {"id", "name"}. Поля, которых не было
        в запросе, выходят как None.
        """
        if isinstance(value, DotModel):
            if depth <= 0:
                return {"id": value.id, "name": getattr(value, "name", None)}
            return {
                name: cls._to_plain(getattr(value, name), depth - 1)
                for name, field in value.get_public_fields().items()
                if not isinstance(field, Binary)
            }
        if isinstance(value, list):
            return [cls._to_plain(item, depth) for item in value]
        return value

    @classmethod
    async def record_context(cls, model_cls, record_id: int) -> dict:
        """Общий контекст документа по записи: все поля записи, связи
        Many2one и списки One2many/Many2many — на один уровень вглубь.

        Значения сырые (дата, Decimal): форматирование — фильтрами шаблона
        {{ x|money }}, {{ x|date }}, {{ x|datetime }}; конструктор ставит их
        сам по типу поля.
        """
        names, nested = cls._context_fields(model_cls)
        record = await model_cls.search_one(
            filter=[("id", "=", record_id)],
            fields=names,
            fields_nested=nested,
        )
        if not record:
            raise RecordNotFound(model_cls.__table__, record_id)
        # Сама запись + один уровень связей
        return cls._to_plain(record, 2)

    @classmethod
    async def _build_context(
        cls, tmpl: "ReportTemplate", template_bytes: bytes, params: dict
    ) -> dict:
        """Данные шаблона: контекст записи (для report_type=record) плюс
        дикты функций данных, чьи ключи стоят в тегах шаблона; функции
        побеждают при совпадении ключей. Из params функция получает только
        свои аргументы (все — если принимает **kwargs)."""
        model_cls = cls.resolve_model(tmpl.model_name)
        record_id = params.get("record_id")
        with_record = tmpl.report_type != "summary" and bool(record_id)
        funcs = cls.data_functions(model_cls, with_record)
        # Опечатка в имени параметра — ошибка, а не молча отчёт по умолчанию
        unknown = set(params) - set(cls.data_params(funcs)) - {"record_id"}
        if unknown and not any(map(cls.takes_kwargs, funcs)):
            raise ValueError(
                f"Unknown report params: {', '.join(sorted(unknown))}"
            )
        tags = await asyncio.to_thread(
            DocxReportEngine.template_tags, template_bytes
        )
        funcs = [f for f in funcs if not tags.isdisjoint(f._report_fields)]
        # Сводный отчёт собирается только из функций: без них — пустой файл
        if tmpl.report_type == "summary" and not funcs:
            raise ValueError("No data function matches the template tags")
        context: dict = {}
        if with_record:
            context.update(await cls.record_context(model_cls, record_id))
        for func in funcs:
            if cls.takes_kwargs(func):
                kwargs = params
            else:
                accepted = inspect.signature(func).parameters
                kwargs = {k: v for k, v in params.items() if k in accepted}
            context.update(await func(env, **kwargs))
        return context

    # ------------------------------------------------------------------
    # Сборка отчёта
    # ------------------------------------------------------------------

    @classmethod
    async def render_bytes(
        cls,
        tmpl: "ReportTemplate",
        template_bytes: bytes,
        params: dict | None,
        output_format: str | None,
    ) -> Attachment:
        """Собрать отчёт из байтов DOCX по настройкам шаблона: НЕсохранённый
        Attachment (name, mimetype, content). Общий путь для сохранённого
        файла (render_attachment) и превью конструктора (report_docx_design).
        """
        params = params or {}
        context = await cls._build_context(tmpl, template_bytes, params)
        fmt = output_format or tmpl.output_format or "docx"
        ext = "pdf" if fmt == "pdf" else "docx"
        # Документ по записи — с её id, сводный отчёт — с датой сборки
        suffix = params.get("record_id") or datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d")
        stem = f"{tmpl.name or 'report'}_{suffix}"
        # docxtpl и LibreOffice синхронные и небыстрые — не держим event loop
        file_bytes, content_type = await asyncio.to_thread(
            DocxReportEngine.generate, template_bytes, context, fmt, stem
        )
        return env.models.attachment(
            name=f"{stem}.{ext}",
            mimetype=content_type,
            size=len(file_bytes),
            content=file_bytes,
        )

    @classmethod
    async def render_attachment(
        cls,
        template_id: int,
        params: dict | None = None,
        output_format: str | None = None,
    ) -> Attachment:
        """Собрать отчёт по сохранённому шаблону.

        Единый путь для скачивания (роут /reports/generate) и рассылок (cron):
        шаблон → контекст (record_context + функции данных по тегам шаблона)
        → docxtpl → при pdf конверсия (см. DocxReportEngine).

        RecordNotFound — нет шаблона/записи; ValueError — ошибка настройки
        шаблона или данных; RuntimeError — конверсия в PDF.
        """
        tmpl = await cls.get_template(template_id)
        attachment = None
        if tmpl.template_file:
            attachment = await env.models.attachment.search_one(
                filter=[("id", "=", tmpl.template_file.id)],
            )
        if not attachment:
            raise ValueError("Template has no DOCX file attached")
        template_bytes = await attachment.read_content()
        if not template_bytes:
            raise ValueError("Could not read template file from storage")
        return await cls.render_bytes(
            tmpl, template_bytes, params, output_format
        )

    # ------------------------------------------------------------------
    # Отправка по расписанию — методы для cron.
    #
    # Cron исполняет только «модель + метод» (произвольный код отключён — RCE),
    # поэтому код «собрать отчёт и отправить» живёт здесь, а задача хранит
    # лишь имя метода и kwargs: template_id, адрес и params функции данных
    # (например {"days": 7}). Задачи-примеры создаёт sales_report_docx
    # выключенными.
    # ------------------------------------------------------------------

    @classmethod
    async def cron_send_report_email(
        cls,
        template_id: int,
        to: str,
        params: dict | None = None,
        subject: str = "",
        text: str = "",
        connector_id: int | None = None,
    ) -> None:
        """Собрать отчёт по шаблону и отправить письмом с вложением через
        email-коннектор чата (SMTP). params — параметры функции данных
        шаблона; connector_id — если email-коннекторов несколько."""
        report = await cls.render_attachment(template_id, params)
        connector = await cls._find_connector("email", connector_id)
        # Тема и текст письма едут внутри body — формат email-стратегии
        body = json.dumps({"subject": subject or report.name, "html": text})
        await connector.strategy.chat_send_message(
            connector,
            connector.outbox_account_id,
            body,
            chat_id=to,
            attachments=[report],
        )
        log.info("Report %s sent by email to %s", report.name, to)

    @classmethod
    async def cron_send_report_telegram(
        cls,
        template_id: int,
        chat_id: str,
        params: dict | None = None,
        text: str = "",
        connector_id: int | None = None,
    ) -> None:
        """Собрать отчёт по шаблону и отправить файлом в Telegram через
        коннектор бота. chat_id — id чата или пользователя Telegram, где бот
        состоит (свой id подскажет @userinfobot)."""
        report = await cls.render_attachment(template_id, params)
        connector = await cls._find_connector("telegram", connector_id)
        strategy = connector.strategy
        if text:
            await strategy.chat_send_message(
                connector, connector.outbox_account_id, text, chat_id=chat_id
            )
        await strategy.chat_send_message_binary(
            connector, connector.outbox_account_id, chat_id, report
        )
        log.info("Report %s sent to Telegram chat %s", report.name, chat_id)

    @staticmethod
    async def _find_connector(connector_type: str, connector_id: int | None):
        """Активный коннектор чата нужного типа (или заданный явно)."""
        connector = await env.models.chat_connector.search_one(
            filter=(
                [("id", "=", connector_id)]
                if connector_id
                else [("type", "=", connector_type), ("active", "=", True)]
            ),
            fields_nested={
                "outbox_account_id": {"fields": ["id", "external_id"]},
            },
        )
        if not connector:
            raise ValueError(
                f"No active chat connector of type '{connector_type}'"
            )
        return connector
