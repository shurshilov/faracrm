# Copyright 2025 FARA CRM
# Attachments module - Route model for organizing files in folders
# OPTIMIZED: priority-based routing, folder cache in separate table

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

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

if TYPE_CHECKING:
    from .attachments import Attachment
    from .attachments_storage import AttachmentStorage

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

    model: str | None = Char(
        string="Model",
        help="Model name (e.g., 'sale', 'lead'). None = fallback route",
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

    # ========================================================================
    # Template rendering
    # ========================================================================

    def _zfill(self, value: Any, width: int = 7) -> str:
        """Zero-fill a value to specified width."""
        return str(value).zfill(width)

    def _render_template(
        self,
        template: str,
        record: Optional[Any] = None,
        extra_context: Optional[Dict[str, Any]] = None,
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

        # Для дефолтного маршрута model берём из extra_context (res_model)
        model_name = self.model
        if not model_name and extra_context:
            model_name = extra_context.get("res_model")

        context = {
            "model": model_name or "",
            "table": model_name.replace(".", "_") if model_name else "",
            "route_id": self.id,
        }

        # Add record fields if provided
        if record:
            context["id"] = getattr(record, "id", "")
            context["zfill"] = lambda x, w=7: self._zfill(x, w)

            # Add all record attributes
            for attr in dir(record):
                if not attr.startswith("_"):
                    try:
                        value = getattr(record, attr)
                        if not callable(value):
                            context[attr] = value
                    except Exception:
                        pass

        # Add extra context
        if extra_context:
            context.update(extra_context)

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
        except KeyError as e:
            logger.warning(f"Missing variable in template: {e}")
            result = template

        return result

    def render_root_folder_name(self, res_model: Optional[str] = None) -> str:
        """Render the root folder name for this route."""
        extra_context = {"res_model": res_model} if res_model else None
        return self._render_template(
            self.pattern_root, extra_context=extra_context
        )

    def render_record_folder_name(
        self,
        record: Any,
        res_model: Optional[str] = None,
        res_id: Optional[int] = None,
    ) -> str:
        extra_context = {}
        if res_model:
            extra_context["res_model"] = res_model
        if res_id:
            extra_context["id"] = res_id
        return self._render_template(
            self.pattern_record, record, extra_context or None
        )

    # ========================================================================
    # Route matching - priority based
    # ========================================================================

    @classmethod
    async def get_route_for_attachment(
        cls,
        res_model: str,
        res_id: int,
    ) -> Optional["AttachmentRoute"]:
        """
        Find matching route using priority-based matching.

        Logic:
        1. First check specific routes (model=res_model) by priority DESC
        2. Then fallback routes (model=None) by priority DESC

        This ensures specific routes always take precedence over fallback,
        regardless of priority values.
        """
        # 1. Try specific routes first (model matches)
        specific_routes = await cls.search(
            filter=[
                ("active", "=", True),
                ("model", "=", res_model),
            ],
            # fields_nested={"storage_id": ["id", "type", "active"]},
            sort="priority DESC",
        )

        for route in specific_routes:
            if await route._check_record_in_filter(res_id):
                return route

        # 2. Then try fallback routes (model=None)
        fallback_routes = await cls.search(
            filter=[
                ("active", "=", True),
                ("model", "=", None),
            ],
            sort="priority DESC",
        )

        if fallback_routes:
            return fallback_routes[0]

        return None

    async def _check_record_in_filter(self, res_id: int) -> bool:
        if isinstance(self.filter, list) and self.filter and self.model:
            ids = await env.models._get_model(self.model).search(
                filter=self.filter
            )
            return res_id in ids
        return True

    async def _get_records_ids(self) -> List[int]:
        if isinstance(self.filter, list) and self.filter and self.model:
            record_ids = await env.models._get_model(self.model).search(
                filter=self.filter, fields=["id"]
            )
            return [record.id for record in record_ids]
        return []

    # ========================================================================
    # Folder cache (uses separate table)
    # ========================================================================

    def _get_cache_key(self, res_model: Optional[str] = None) -> str:
        if self.model is not None:
            return "_default"
        return res_model or "_default"

    async def _get_cached_root_folder(
        self, res_model: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        from .attachments_cache import AttachmentCache

        cache_key = self._get_cache_key(res_model)
        return await AttachmentCache.get_folder(self.id, cache_key)

    async def _save_root_folder_to_cache(
        self,
        folder_id: str,
        folder_name: str,
        res_model: Optional[str] = None,
    ) -> None:
        from .attachments_cache import AttachmentCache

        cache_key = self._get_cache_key(res_model)
        await AttachmentCache.set_folder(
            route_id=self.id,
            res_model=cache_key,
            folder_id=folder_id,
            folder_name=folder_name,
        )

    # ========================================================================
    # Folder management
    # ========================================================================

    async def get_or_create_root_folder(
        self,
        storage: "AttachmentStorage",
        res_model: str | None = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get or create root folder for this route."""
        # Check cache first
        folder_id, folder_name = await self._get_cached_root_folder(res_model)
        if folder_id:
            return folder_id, folder_name

        # Render folder name
        folder_name = self.render_root_folder_name(res_model)
        if not folder_name:
            folder_name = self.model or res_model
            if not folder_name:
                raise ValueError("Cant setup empty folder_name")

        # Get strategy and create folder
        strategy = get_strategy(storage.type)

        parent_id = None
        if hasattr(strategy, "_get_parent_id"):
            parent_id = strategy._get_parent_id(storage)

        metadata = {
            "route_id": str(self.id),
            "res_model": self.model or res_model,
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
            await self._save_root_folder_to_cache(
                folder_id, folder_name, res_model
            )

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
            return None, None

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

        folder_id, old_name = await self._get_cached_root_folder()
        if not folder_id:
            return

        new_name = self.render_root_folder_name()
        if new_name and new_name != old_name:
            strategy = get_strategy(storage.type)

            if hasattr(strategy, "rename_folder"):
                await strategy.rename_folder(
                    storage=storage,
                    folder_id=folder_id,
                    new_name=new_name,
                )

            await self._save_root_folder_to_cache(folder_id, new_name)

            await self.update(
                AttachmentRoute(need_sync_root_name=False)
            )

    async def get_attachments_to_sync(
        self,
        storage_id: int,
    ) -> List[int]:
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
            ("res_model", "=", self.model),
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
        cls, storage_id: int
    ) -> "AttachmentRoute":
        """
        Ensure a default route exists for a storage.

        Creates a default route if one doesn't exist.

        Args:
            storage_id: Storage ID

        Returns:
            Default route for the storage
        """
        # Check if default route already exists
        existing = await cls.search(
            filter=[("storage_id", "=", storage_id), ("model", "=", None)],
            limit=1,
        )

        if existing:
            return existing[0]

        default_route = AttachmentRoute()
        default_route.name = "Default Route"
        default_route.model = None
        default_route.priority = 0
        default_route.pattern_root = "{model}"
        default_route.pattern_record = "{id}-{name}"
        default_route.flat = False
        default_route.storage_id = env.models.attachment_storage(id=storage_id)
        default_route.active = True

        default_route.id = await cls.create(default_route)
        return default_route

    # ========================================================================
    # Hooks
    # ========================================================================

    async def after_delete(self) -> None:
        from .attachments_cache import AttachmentCache

        await AttachmentCache.clear_route_cache(self.id)
