from typing import TYPE_CHECKING
import logging

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)


class AttachmentsApp(App):
    """
    Приложение добавляет вложения и файлы
    """

    info = {
        "name": "Attachments",
        "summary": "Module allow work with binary data. Local and remote files.",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "attachment": ACL.FULL,
        "attachment_storage": ACL.READ_ONLY,
        "attachment_route": ACL.READ_ONLY,
        "attachment_cache": ACL.READ_ONLY,
    }
    ROLE_ACL = {
        "system_admin": {
            "attachment": ACL.FULL,
            "attachment_storage": ACL.FULL,
            "attachment_route": ACL.FULL,
            "attachment_cache": ACL.FULL,
        },
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        await self._init_system_settings(env)
        await self._init_default_storage(env)
        await self._init_default_routes(env)
        await self._init_polymorphic_rules(env)
        await self._init_default_saved_filters(env)

    async def _init_default_saved_filters(self, env: "Environment"):
        """
        Создаёт дефолтные сохранённые фильтры для модели attachments.

        Фильтр «Мои файлы» применяется при первой загрузке списка
        /attachments — пользователь видит только записи где он автор
        (create_user_id == текущий пользователь). Это чисто визуальная
        фильтрация поверх ACL: фильтр снимается крестиком в панели
        поиска, и пользователь увидит все доступные ему файлы.

        Подстановка {{user_id}} происходит на фронте при применении
        savedFilter (см. useSearchFilter), а не на бэке: filter_data
        хранится как шаблон-строка и одинаковая запись в БД работает
        для всех пользователей.
        """
        import json
        from backend.base.system.saved_filters.models.saved_filter import (
            SavedFilter,
        )

        FILTER_NAME = "Мои файлы"
        MODEL_NAME = "attachments"
        FILTER_DATA = [
            ["create_user_id", "=", "{{user_id}}"],
        ]

        existing = await env.models.saved_filter.search(
            filter=[
                ("model_name", "=", MODEL_NAME),
                ("name", "=", FILTER_NAME),
                ("is_global", "=", True),
            ],
            limit=1,
        )

        expected_filter_data = json.dumps(FILTER_DATA)

        if existing:
            current = existing[0]
            if current.filter_data == expected_filter_data:
                # Формат совпадает — ничего не делаем.
                return
            await current.delete()

        await env.models.saved_filter.create(
            payload=SavedFilter(
                name=FILTER_NAME,
                model_name=MODEL_NAME,
                filter_data=expected_filter_data,
                user_id=None,
                is_global=True,
                is_default=True,
            ),
        )

    async def _init_polymorphic_rules(self, env: "Environment"):
        """
        Создаёт rules для полиморфного доступа к attachments.

        Используется один универсальный оператор @has_polymorphic_parent_access,
        который сам определяет какие res_model встречаются в БД и
        параллельно проверяет доступ к каждой родительской модели через
        её собственные rules. Это покрывает ВСЕ возможные типы вложений
        автоматически:

          - vложения чат-сообщений (parent = chat_message → @is_member)
          - вложения партнёров (parent = partner → нет rules → видны всем)
          - вложения лидов (parent = lead → ownership rules)
          - вложения новых типов (без необходимости менять код)

        Дополнительный rule для public=True файлов — видны всем
        залогиненным независимо от parent.
        """
        from backend.base.crm.security.models.rules import Rule

        async def create_rule_if_missing(name, domain, perms):
            attachment_model = await env.models.model.search(
                filter=[("name", "=", "attachment")],
                limit=1,
            )
            if not attachment_model:
                logger.warning("Model 'attachment' not found")
                return
            existing = await env.models.rule.search(
                filter=[("name", "=", name)],
                limit=1,
            )
            if existing:
                return
            await env.models.rule.create(
                payload=Rule(
                    name=name,
                    active=True,
                    model_id=attachment_model[0],
                    role_id=None,
                    domain=domain,
                    perm_create=perms.get("create", False),
                    perm_read=perms.get("read", False),
                    perm_update=perms.get("update", False),
                    perm_delete=perms.get("delete", False),
                ),
            )

        # Public-вложения видны всем залогиненным
        await create_rule_if_missing(
            name="Attachment: public files visible to everyone",
            domain=[["public", "=", True]],
            perms={"read": True},
        )

        # Универсальный rule: видишь parent — видишь его вложения.
        # Полиморфный оператор:
        #   - сам узнаёт какие res_model встречаются (DISTINCT)
        #   - параллельно через asyncio.gather проверяет доступ
        #     к каждой родительской модели через её собственные rules
        #   - возвращает OR-domain покрывающий все типы родителей
        #
        # Не нужно явно прописывать rule для chat_message, lead, partner и
        # каждой будущей res_model. Если у родителя есть rules
        # (как у chat_message — @is_member) — они применятся. Если нет —
        # доступ открыт всем у кого есть ACL на родителя (как у partner).
        await create_rule_if_missing(
            name="Attachment: visible if parent record is accessible",
            domain=[["@has_polymorphic_parent_access", "res_model", "res_id"]],
            perms={"read": True, "update": True},
        )

    async def _init_system_settings(self, env: "Environment"):
        """Создаёт настройки по умолчанию для модуля attachments."""
        import os

        await env.models.system_settings.ensure_defaults(
            [
                {
                    "key": "attachments.filestore_path",
                    "value": {"value": os.path.join(os.getcwd(), "filestore")},
                    "description": "Путь к локальному хранилищу файлов",
                    "module": "attachments",
                    "is_system": False,
                    "cache_ttl": -1,
                },
            ]
        )

    async def _init_default_storage(self, env: "Environment"):
        """Создаёт дефолтное хранилище типа file (id=1)."""
        storage = await env.models.attachment_storage.search(
            filter=[("id", "=", 1)], limit=1
        )
        if not storage:
            from backend.base.crm.attachments.models.attachments_storage import (
                AttachmentStorage,
            )

            await env.models.attachment_storage.create(
                payload=AttachmentStorage(
                    name="Local File Storage",
                    type="file",
                    active=True,
                ),
            )

    async def _init_default_routes(self, env: "Environment"):
        """Создаёт дефолтные маршруты для всех хранилищ."""
        from backend.base.crm.attachments.models.attachments_route import (
            AttachmentRoute,
        )

        storages = await env.models.attachment_storage.search(filter=[])
        for storage in storages:
            if storage.type == "file":
                await AttachmentRoute.ensure_default_route_for_storage(storage)
