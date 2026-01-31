# Copyright 2025 FARA CRM
# Attachments module - Route model for organizing files in folders

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

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
        help="Model name (e.g., 'sale', 'lead', 'partner')",
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

    filter: dict | list = JSONField(
        string="Filter",
        default=None,
        help="""JSON filter for records to sync.
        Example: [["active", "=", true], ["state", "=", "done"]]
        """,
    )

    folder_id: str | None = Char(
        string="Cloud folder ID",
        help="ID of the root folder in cloud storage. Set automatically.",
    )

    folder_model_name: str | None = Char(
        string="Folder model name",
        help="Cached rendered name of the root folder.",
    )

    need_sync_root_name: bool = Boolean(
        string="Need sync root name",
        default=False,
        help="Flag to sync root folder name on next sync.",
    )

    storage_id: "AttachmentStorage" = Many2one(
        relation_table=lambda: env.models.attachment_storage,
        string="Storage",
        help="Storage where file is saved",
    )

    active: bool = Boolean(
        string="Active",
        default=True,
    )

    is_default: bool = Boolean(
        string="Default route",
        default=False,
        help="Use as fallback when no specific route matches the model. "
        "Default route should have model=None.",
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
        self, record: Any, res_model: Optional[str] = None
    ) -> str:
        """Render the record folder name for a specific record."""
        extra_context = {"res_model": res_model} if res_model else None
        return self._render_template(
            self.pattern_record, record, extra_context
        )

    # ========================================================================
    # Route matching
    # ========================================================================

    @classmethod
    async def get_route_for_attachment(
        cls,
        storage_id: int,
        res_model: str,
        res_id: int,
    ) -> Optional["AttachmentRoute"]:
        """
        Find matching route for an attachment.

        Priority:
        1. Specific route for the model (model = res_model) with filter check
        2. Default route (is_default = True) - no filter check

        Args:
            storage_id: Storage ID
            res_model: Resource model name
            res_id: Resource record ID

        Returns:
            Matching route or None
        """
        # 1. Find specific route for this model and storage
        routes = await cls.search(
            filter=[
                ("model", "=", res_model),
                ("storage_id", "=", storage_id),
                ("active", "=", True),
                ("is_default", "=", False),
            ],
        )

        for route in routes:
            # Check if record matches filter
            if await route._check_record_in_filter(res_id):
                return route

        # 2. Fallback to default route (no filter check)
        default_routes = await cls.search(
            filter=[
                ("is_default", "=", True),
                ("storage_id", "=", storage_id),
                ("active", "=", True),
            ],
            limit=1,
        )

        if default_routes:
            return default_routes[0]

        return None

    async def _check_record_in_filter(self, res_id: int) -> bool:
        """
        Check if record matches route filter.

        Args:
            res_id: Record ID to check

        Returns:
            True if record matches filter or filter is empty
        """

        if isinstance(self.filter, list) and self.filter and self.model:
            ids = await env.models._get_model(self.model).search(
                filter=self.filter
            )
            return res_id in ids
        else:
            return True

    async def _get_records_ids(self):
        """Return records for process sync"""
        if isinstance(self.filter, list) and self.filter and self.model:
            record_ids = await env.models._get_model(self.model).search(
                filter=self.filter, fields=["id"]
            )
            return [record.id for record in record_ids]
        else:
            return []

    # ========================================================================
    # Folder management
    # ========================================================================

    async def get_or_create_root_folder(
        self,
        storage: "AttachmentStorage",
        res_model: str | None = None,
    ) -> str | None:
        """
        Get or create root folder for this route.

        Args:
            storage: Storage to create folder in
            res_model: Model name from attachment (for default routes)

        Returns:
            Folder ID
        """

        # Return cached folder_id if exists (only for non-default routes)
        if self.folder_id and not self.is_default:
            return self.folder_id

        # Render folder name (uses res_model for default routes)
        folder_name = self.render_root_folder_name(res_model)
        if not folder_name:
            folder_name = self.model or res_model

        # Cache the name
        self.folder_model_name = folder_name

        # Get strategy and create folder
        strategy = get_strategy(storage.type)

        # Get parent folder from storage
        parent_id = None
        if hasattr(strategy, "_get_parent_id"):
            parent_id = strategy._get_parent_id(storage)

        # Create folder with metadata
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

        if folder_id and not self.is_default:
            # Save folder_id (only for non-default routes)
            update_data = AttachmentRoute()
            update_data.folder_id = folder_id
            update_data.folder_model_name = folder_name
            await self.update(update_data)
            self.folder_id = folder_id

        return folder_id

    async def get_or_create_record_folder(
        self,
        storage: "AttachmentStorage",
        record: Any,
        res_id: int,
        res_model: str,
    ) -> Optional[str]:
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

        # Ensure root folder exists
        root_folder_id = await self.get_or_create_root_folder(
            storage, res_model
        )
        if not root_folder_id:
            return None

        # Render record folder name
        folder_name = self.render_record_folder_name(record, res_model)
        if not folder_name:
            folder_name = str(res_id)

        # Get strategy and create folder
        strategy = get_strategy(storage.type)

        # Create folder with metadata
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

        return folder_id

    # ========================================================================
    # Sync methods
    # ========================================================================

    async def sync_root_folder_name(
        self, storage: "AttachmentStorage"
    ) -> None:
        """
        Sync root folder name if it was changed.

        Args:
            storage: Storage
        """
        if not self.need_sync_root_name or not self.folder_id:
            return

        new_name = self.render_root_folder_name()
        if new_name and new_name != self.folder_model_name:
            strategy = get_strategy(storage.type)

            # Update folder name in cloud
            if hasattr(strategy, "rename_folder"):
                await strategy.rename_folder(
                    storage=storage,
                    folder_id=self.folder_id,
                    new_name=new_name,
                )

            # Update cached name and reset flag
            update_data = AttachmentRoute()
            update_data.folder_model_name = new_name
            update_data.need_sync_root_name = False
            await self.update(update_data)

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
        cls,
        storage_id: int,
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
            filter=[
                ("storage_id", "=", storage_id),
                ("is_default", "=", True),
            ],
            limit=1,
        )

        if existing:
            return existing[0]

        # Create default route
        default_route = AttachmentRoute()
        default_route.name = "Default Route"
        default_route.model = None
        default_route.is_default = True
        default_route.pattern_root = "{model}"
        default_route.pattern_record = "{id}-{name}"
        default_route.flat = False
        default_route.storage_id = env.models.attachment_storage(id=storage_id)
        default_route.active = True

        default_route.id = await cls.create(default_route)
        return default_route
