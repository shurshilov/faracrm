# Copyright 2025 FARA CRM
# Attachments module - Route model for organizing files in folders
# OPTIMIZED: priority-based routing, folder cache in separate table

import logging
import re
from typing import TYPE_CHECKING, Any

from backend.base.system.dotorm.dotorm.fields import (
    Boolean,
    Char,
    Integer,
    JSONField,
    Many2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.crm.attachments.strategies import get_strategy
from .attachments_cache import AttachmentCache

if TYPE_CHECKING:
    from .attachments_storage import AttachmentStorage
    from backend.base.crm.security.models.models import Model

logger = logging.getLogger(__name__)


class AttachmentRoute(DotModel):
    """
    Модель маршрутов для организации файлов в облачных хранилищах.

    Маршрут определяет:
    - Какая модель (res_model) обрабатывается
    - Как называть корневую папку модели (pattern_root)
    - Как называть папку записи (pattern_record)
    - Фильтрация записей для синхронизации

    Пример структуры папок:
        Google Drive/
        └── Sales Orders/           <- pattern_root: "Sales Orders"
            ├── SO-0000001-Client A/ <- pattern_record: "SO-{zfill(id)}-{name}"
            │   ├── contract.pdf
            │   └── invoice.pdf
            └── SO-0000002-Client B/
                └── proposal.docx
    """

    __table__ = "attachments_route"

    id: int = Integer(primary_key=True)

    name: str = Char(
        string="Route Name",
        help="Human readable name for the route",
    )

    # РАНЬШЕ было текстовое поле `model` (имя таблицы строкой). Теперь связь на
    # реестр моделей — чтобы выбирать модель из списка, а не печатать вручную.
    # Пусто (NULL) = fallback-маршрут для всех моделей (как раньше model=None).
    model_id: "Model | None" = Many2one(
        relation_table=lambda: env.models.model,
        string="Model",
        help="Model (from models registry). Empty = fallback route for all models",
    )

    priority: int = Integer(
        string="Priority",
        default=10,
        help="Higher priority routes are checked first. Fallback = 0",
    )

    pattern_root: str = Char(
        string="Root folder pattern",
        default="{model}",
        help="""Template for root (model) folder name.
        Available variables:
        - {model} - model name
        - {table} - table name
        Example: "Sales Orders" or "{model}"
        """,
    )

    pattern_record: str = Char(
        string="Record folder pattern",
        default="{id}",
        help="""Template for record folder name.
        Available variables:
        - {id} - record ID
        - {zfill(id)} - record ID with leading zeros (7 digits)
        - {field_name} - any field from the record (e.g., {name}, {code})
        Example: "{zfill(id)}-{name}" -> "0000001-John Doe"
        """,
    )

    flat: bool = Boolean(
        string="Flat structure",
        default=False,
        help="""If True - all files go directly to root folder without subfolders.
        If False - create subfolder for each record.
        """,
    )

    filter: dict | list | None = JSONField(
        string="Filter",
        default=None,
        help="""JSON filter for records to sync.
        Example: [["active", "=", true], ["state", "=", "done"]]
        """,
    )

    need_sync_root_name: bool = Boolean(
        string="Need sync root name",
        default=False,
        help="Flag to sync root folder name on next sync.",
    )

    storage_id: "AttachmentStorage" = Many2one(
        relation_table=lambda: env.models.attachment_storage,
        string="Storage",
    )

    active: bool = Boolean(
        string="Active",
        default=True,
    )

    def _model_table(self) -> str | None:
        """Имя таблицы модели маршрута (аналог прежнего self.model), либо None.

        model_id.table_name заполняется при сидинге реестра (_init_models), а
        search грузит store-поля связи — поэтому имя таблицы доступно напрямую.
        res_model вложений — тоже имя таблицы, сравнения/фильтры корректны.
        (Поле названо table_name, а не table: table — зарезервированное слово.)
        """
        return self.model_id.table_name if self.model_id else None

    # ========================================================================
    # Template rendering
    # ========================================================================

    def _zfill(self, value: Any, width: int = 7) -> str:
        """Zero-fill a value to specified width."""
        return str(value).zfill(width)

    def _render_template(
        self,
        template: str,
        record: DotModel | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> str:
        """
        Render a template string with variables.

        Args:
            template: Template string with {variable} placeholders
            record: Record object to get field values from
            extra_context: Additional variables for rendering

        Returns:
            Rendered string
        """
        if not template:
            return ""

        # Для дефолтного маршрута model берём из extra_context (res_model).
        # Раньше здесь было self.model (текст); теперь модель — связь, поэтому
        # имя таблицы получаем из model_id (None у дефолтного маршрута).
        model_name = self._model_table()
        context = {
            "model": model_name or "",
            "route_id": self.id,
        }
        # Add extra context
        if extra_context:
            context.update(extra_context)
            if not model_name:
                model_name = extra_context.get("res_model")

        # {table} — имя таблицы модели (для дефолтного маршрута = res_model).
        # Токен статичный, добавлен для конструктора корневой папки на фронте.
        context.setdefault("table", model_name or "")

        # Add record fields if provided
        if record:
            # Add all record attributes
            for field_name in record.get_all_fields().keys():
                if record.is_assigned(field_name):
                    context[field_name] = getattr(record, field_name)

        # Handle zfill function calls in template
        # Convert {zfill(id)} to actual zfill call
        def replace_zfill(match):
            var_name = match.group(1)
            value = context.get(var_name, "")
            return self._zfill(value)

        template = re.sub(r"\{zfill\((\w+)\)\}", replace_zfill, template)

        # Simple variable substitution
        try:
            result = template.format(**context)
        except KeyError:
            # У модели нет такого поля (у chat_message нет name) — папка по id.
            # Иначе шаблон возвращался как есть и становился именем папки,
            # общим для ВСЕХ записей модели: файлы с совпавшими именами
            # ложились рядом и затирали друг друга.
            result = str(context.get("id", ""))

        return result

    def render_root_folder_name(self, res_model: str | None = None) -> str:
        """Render the root folder name for this route."""
        extra_context = {"res_model": res_model} if res_model else None
        return self._render_template(
            self.pattern_root, extra_context=extra_context
        )

    def render_record_folder_name(
        self,
        record: Any,
        res_model: str | None = None,
        res_id: int | None = None,
    ) -> str:
        extra_context = {}
        if res_model:
            extra_context["res_model"] = res_model
        if res_id:
            extra_context["id"] = res_id
        return self._render_template(
            self.pattern_record, record, extra_context
        )

    # ========================================================================
    # Route matching - priority based
    # ========================================================================

    @classmethod
    async def get_route_for_attachment(
        cls,
        res_model: str | None,
        res_id: int | None,
    ):
        """
        Find matching route using priority-based matching.

        Logic:
        1. First check specific routes (model=res_model) by priority DESC
        2. Then fallback routes (model=None) by priority DESC

        This ensures specific routes always take precedence over fallback,
        regardless of priority values.
        """
        if res_model and res_id:
            # 1. Try specific routes first (model matches)
            # res_model — имя таблицы; в реестре хранится models.table_name,
            # поэтому находим запись реестра напрямую по table_name.
            model_rec = await env.models.model.search_one(
                filter=[("table_name", "=", res_model)], fields=["id"]
            )

            if model_rec:
                specific_routes = await cls.search(
                    filter=[
                        ("active", "=", True),
                        ("model_id", "=", model_rec.id),
                    ],
                    # fields_nested={"storage_id": ["id", "type", "active"]},
                    sort="priority",
                    order="DESC",
                )

                for route in specific_routes:
                    if await route._check_record_in_filter(res_id):
                        return route

        # 2. Then try fallback routes (model=None)
        fallback_routes = await cls.search(
            filter=[
                ("active", "=", True),
                ("model_id", "=", None),
            ],
            sort="priority",
            order="DESC",
        )

        if fallback_routes:
            return fallback_routes[0]

        return None

    async def _check_record_in_filter(self, res_id: int) -> bool:
        if isinstance(self.filter, list) and self.filter and self.model_id:
            ids = await env.models._get_model(self.model_id.name).search(
                filter=self.filter
            )
            return res_id in ids
        return True

    async def _get_records_ids(self) -> list[int]:
        if isinstance(self.filter, list) and self.filter and self.model_id:
            record_ids = await env.models._get_model(
                self.model_id.name
            ).search(filter=self.filter, fields=["id"])
            return [record.id for record in record_ids]
        return []

    # ========================================================================
    # Folder management
    # ========================================================================

    async def get_or_create_root_folder(
        self, storage: "AttachmentStorage", res_model: str
    ):
        """Get or create root folder for this route."""
        # Check cache first
        folder_id, folder_name = await AttachmentCache.get_folder(
            self.id, res_model
        )
        if folder_id and folder_name:
            return folder_id, folder_name

        # Render folder name
        folder_name = (
            self.render_root_folder_name(res_model)
            or self._model_table()
            or res_model
        )

        # Get strategy and create folder
        strategy = get_strategy(storage.type)

        # используется в облачных хранилищах
        parent_id = strategy._get_parent_id(storage)

        metadata = {
            "route_id": str(self.id),
            "res_model": self._model_table() or res_model,
            "storage_id": str(storage.id),
        }

        folder_id = await strategy.create_folder(
            storage=storage,
            folder_name=folder_name,
            parent_id=parent_id,
            metadata=metadata,
        )

        # Save to cache
        if folder_id:
            await AttachmentCache.set_folder(
                route_id=self.id,
                res_model=res_model,
                folder_id=folder_id,
                folder_name=folder_name,
            )
        else:
            raise ValueError("Cant setup empty folder_id")

        return folder_id, folder_name

    async def get_or_create_record_folder(
        self,
        storage: "AttachmentStorage",
        record: Any,
        res_id: int,
        res_model: str,
    ):
        """
        Get or create record folder within route's root folder.

        Args:
            storage: Storage
            record: Record object
            res_id: Record ID
            res_model: Model name

        Returns:
            Folder ID for the record
        """

        # For flat structure, return root folder
        if self.flat:
            return await self.get_or_create_root_folder(storage, res_model)

        root_folder_id, _ = await self.get_or_create_root_folder(
            storage, res_model
        )
        if not root_folder_id:
            raise ValueError("Cant setup empty root_folder_id")

        folder_name = self.render_record_folder_name(record, res_model, res_id)
        if not folder_name:
            folder_name = str(res_id)

        strategy = get_strategy(storage.type)

        metadata = {
            "route_id": str(self.id),
            "res_model": res_model,
            "res_id": str(res_id),
            "storage_id": str(storage.id),
        }

        folder_id = await strategy.create_folder(
            storage=storage,
            folder_name=folder_name,
            parent_id=root_folder_id,
            metadata=metadata,
        )

        return folder_id, folder_name

    # ========================================================================
    # Sync methods
    # ========================================================================

    async def sync_root_folder_name(
        self, storage: "AttachmentStorage"
    ) -> None:
        if not self.need_sync_root_name:
            return

        folder_id, old_name = await AttachmentCache.get_folder(
            self.id, self._model_table() or "default"
        )
        if not folder_id:
            return

        new_name = self.render_root_folder_name()
        if new_name and new_name != old_name:
            strategy = get_strategy(storage.type)

            # TODO: сделать обновления имени папки
            # await strategy.update_file(
            #     storage=storage,
            #     folder_id=folder_id,
            #     filename=new_name,
            # )

            await AttachmentCache.set_folder(
                route_id=self.id,
                res_model=self._model_table() or "default",
                folder_id=folder_id,
                folder_name=new_name,
            )

            await self.update(AttachmentRoute(need_sync_root_name=False))

    async def get_attachments_to_sync(
        self,
        storage_id: int,
    ):
        """
        Get attachment IDs that should be synced via this route.

        Args:
            storage_id: Storage ID

        Returns:
            List of attachment IDs

        Важно - содержит те вложения которые ДОЛЖНЫ быть в маршруте, но не
        факт что находятся в нем, используется для синхронизации.
        Отличие от _get_records_ids что возвращаются вложения и
        в том что он фильтрует вложения по хранилищу и плюс по типу и модели.
        """
        from .attachments import Attachment

        filter_common = [
            ("res_model", "=", self._model_table()),
            ("storage_id", "in", [None, storage_id]),
            ("storage_file_id", "=", None),
        ]
        # Filter by route filter if needed
        filter_additional = await self._get_records_ids()

        # Get attachments for this model that are not yet synced
        attachments = await Attachment.search(
            filter=filter_common + filter_additional
        )

        return [a.id for a in attachments]

    # ========================================================================
    # Default route management
    # ========================================================================

    @classmethod
    async def ensure_default_route_for_storage(
        cls, storage_id: "AttachmentStorage"
    ):
        """
        Ensure a default route exists for a storage.

        Creates a default route if one doesn't exist.

        Args:
            storage_id: Storage ID

        Returns:
            Default route for the storage
        """
        # Check if default route already exists
        existing = await cls.search_one(
            filter=[
                ("storage_id", "=", storage_id.id),
                ("model_id", "=", None),
            ],
        )

        if existing:
            return existing

        default_route = AttachmentRoute()
        default_route.name = "Default Route"
        # model_id не задаём — fallback-маршрут для всех моделей (было model=None)
        default_route.priority = 0
        default_route.pattern_root = "{model}"
        default_route.pattern_record = "{id}-{name}"
        default_route.flat = False
        default_route.storage_id = storage_id
        default_route.active = True

        default_route.id = await cls.create(default_route)
        return default_route

    # ========================================================================
    # Hooks
    # ========================================================================

    async def after_delete(self) -> None:
        await AttachmentCache.delete_folder(self.id)
