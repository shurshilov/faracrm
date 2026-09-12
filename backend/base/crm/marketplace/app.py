# Copyright 2025 FARA CRM
# Marketplace module - application

from typing import TYPE_CHECKING

from backend.base.system.core.app import App
from backend.base.system.dotorm.dotorm.access import BYPASS_DOMAIN
from backend.base.crm.security.acl_post_init_mixin import ACL, ACLPerms

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

ROLE_CODE = "marketplace_user"
WORKSPACE_NAME = "Маркетплейс"

# Что может любой пользователь маркетплейса (и сотрудник): свои приложения
# — целиком, покупки — создавать и видеть свои. Строки режут правила ниже.
MARKET_ACL = {
    "marketplace_app": ACL.FULL,
    "marketplace_purchase": ACL.CREATE_READ,
}

# Портальная роль НЕ наследует base_user (иначе видела бы партнёров, чаты и
# прочее). Ей выдаётся только то, без чего не работает сам интерфейс: свой
# профиль, языки (меню пользователя), списки с фильтрами/колонками, вложения
# (скриншоты, архивы), свои платежи и свои контакты (подписка на web push —
# это контакт типа web_push на пользователе). Вход/выход и сессия идут мимо
# ACL. contact_type намеренно НЕ выдаётся: через его connector_ids читается
# список коннекторов, а справочник ручки push берут под sudo.
PORTAL_ACL = {
    "user": ACLPerms(create=False, read=True, update=True, delete=False),
    "language": ACL.READ_ONLY,
    "attachment": ACL.FULL,
    "saved_filter": ACL.FULL,
    "column_setting": ACL.FULL,
    "payment": ACL.READ_ONLY,
    "contact": ACL.NO_DELETE,
}

ALL_PERMS = {"create": True, "read": True, "update": True, "delete": True}


class MarketplaceApp(App):
    """
    Маркетплейс приложений: публичный каталог, личный кабинет поставщика
    (приложения, файлы, статистика), покупки через модуль payment.
    Регистрация покупателей/поставщиков — модуль registration.
    """

    info = {
        "ui_menu": True,
        "ui_menu_name": "marketplace",
        # Гость с корня сайта попадает в каталог, а не на форму входа.
        "public_home": "/market",
        "name": "Marketplace",
        "summary": "Apps marketplace: catalog, vendor cabinet, purchases",
        "author": "FARA CRM",
        "category": "Sales",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        # Канал регистрации и провайдер оплаты — в зависимостях явно: без
        # них маркетплейс не пришлёт код и не примет платёж, а ставятся
        # они вместе с ним одной кнопкой.
        "depends": [
            "registration",
            "registration_email",
            "payment",
            "payment_tinkoff",
            "attachments",
            # Архив модуля из GitHub — вложение в git-хранилище.
            "attachments_git",
        ],
        "sequence": 130,
        "post_init": True,
        # Не ставится сам: админ включает маркетплейс на странице
        # «Приложения», зависимости подтянутся.
        "auto_install": False,
    }

    BASE_USER_ACL = MARKET_ACL
    ROLE_ACL = {
        ROLE_CODE: {**MARKET_ACL, **PORTAL_ACL},
        "system_admin": {
            "marketplace_app": ACL.FULL,
            "marketplace_purchase": ACL.FULL,
        },
    }

    async def post_init(self, app: "FastAPI"):
        env: "Environment" = app.state.env
        # Роль нужна раньше ACL: super().post_init создаёт их по коду роли.
        role_id = await self._init_role(env)
        await super().post_init(app)
        await self._init_workspace(env)
        await self._init_rules(env, role_id)
        await self._init_settings(env)

    async def _app_row_id(self, env: "Environment") -> int | None:
        row = await env.models.app.search_one(
            filter=[("code", "=", "marketplace")], fields=["id"]
        )
        return row.id if row else None

    async def _init_role(self, env: "Environment") -> int:
        """Роль marketplace_user — без наследования base_user."""
        from backend.base.crm.security.models.apps import App as AppModel
        from backend.base.crm.security.models.roles import Role

        existing = await env.models.role.search_one(
            filter=[("code", "=", ROLE_CODE)], fields=["id"]
        )
        if existing:
            return existing.id
        app_id = await self._app_row_id(env)
        return await env.models.role.create(
            payload=Role(
                code=ROLE_CODE,
                name="Пользователь маркетплейса",
                app_id=AppModel(id=app_id) if app_id else None,
            )
        )

    async def _init_workspace(self, env: "Environment"):
        """«Рабочее место» с одной плиткой — личным кабинетом маркетплейса."""
        from backend.base.crm.security.models.workspace import Workspace

        app_id = await self._app_row_id(env)
        if not app_id:
            return
        existing = await env.models.workspace.search_one(
            filter=[("name", "=", WORKSPACE_NAME)], fields=["id"]
        )
        if existing:
            ws_id = existing.id
        else:
            ws_id = await env.models.workspace.create(
                payload=Workspace(name=WORKSPACE_NAME, active=True, sequence=3)
            )
        ws = await env.models.workspace.get(ws_id)
        await ws.update(payload=Workspace(app_ids={"selected": [app_id]}))

    async def _init_rules(self, env: "Environment", role_id: int):
        from backend.base.crm.security.models.rules import Rule

        system_admin = await env.models.role.search_one(
            filter=[("code", "=", "system_admin")], fields=["id"]
        )
        admin_id = system_admin.id if system_admin else None
        own_user = [["user_id", "=", "{{user_id}}"]]

        # (имя, модель, роль (None — все), домен, права)
        rules = [
            (
                "Marketplace app: published or own",
                "marketplace_app",
                None,
                [
                    ["published", "=", True],
                    "or",
                    ["create_user_id", "=", "{{user_id}}"],
                ],
                {"read": True},
            ),
            (
                "Marketplace app: vendor manages own",
                "marketplace_app",
                None,
                [["create_user_id", "=", "{{user_id}}"]],
                {"create": True, "update": True, "delete": True},
            ),
            (
                "Marketplace purchase: buyer sees own",
                "marketplace_purchase",
                None,
                own_user,
                {"create": True, "read": True},
            ),
            # Портальная роль: свой профиль, свои фильтры и колонки — те же
            # правила, что у base_user в users / saved_filters / view_settings.
            (
                "Marketplace user: own profile",
                "user",
                role_id,
                [["id", "=", "{{user_id}}"]],
                {"read": True, "update": True},
            ),
            (
                "Marketplace user: own and global saved filters",
                "saved_filter",
                role_id,
                [
                    ["user_id", "=", "{{user_id}}"],
                    "or",
                    ["user_id", "=", None],
                ],
                {"read": True},
            ),
            (
                "Marketplace user: shared saved filters",
                "saved_filter",
                role_id,
                [["is_global", "=", True]],
                {"read": True},
            ),
            (
                "Marketplace user: manages own saved filters",
                "saved_filter",
                role_id,
                own_user,
                {"update": True, "delete": True},
            ),
            (
                "Marketplace user: own column settings",
                "column_setting",
                role_id,
                own_user,
                {"read": True, "update": True, "delete": True},
            ),
            # Контакты только свои (user_id): подписка/отписка web push.
            (
                "Marketplace user: own contacts",
                "contact",
                role_id,
                own_user,
                {"create": True, "read": True, "update": True},
            ),
        ]
        if admin_id:
            rules += [
                (
                    "Marketplace: system admin manages apps",
                    "marketplace_app",
                    admin_id,
                    BYPASS_DOMAIN,
                    ALL_PERMS,
                ),
                (
                    "Marketplace: system admin manages purchases",
                    "marketplace_purchase",
                    admin_id,
                    BYPASS_DOMAIN,
                    ALL_PERMS,
                ),
            ]

        for name, model_name, rule_role_id, domain, perms in rules:
            existing = await env.models.rule.search_one(
                filter=[("name", "=", name)]
            )
            if existing:
                continue
            model = await env.models.model.search_one(
                filter=[("name", "=", model_name)]
            )
            if not model:
                continue
            await env.models.rule.create(
                payload=Rule(
                    name=name,
                    active=True,
                    model_id=model,
                    role_id=rule_role_id,
                    domain=domain,
                    perm_create=perms.get("create", False),
                    perm_read=perms.get("read", False),
                    perm_update=perms.get("update", False),
                    perm_delete=perms.get("delete", False),
                )
            )

    async def _init_settings(self, env: "Environment"):
        """Кого создаёт регистрация: роль и РМ маркетплейса, старт — кабинет."""
        from backend.base.crm.registration.models.registration import (
            NEW_USER_SETTING,
        )

        await env.models.system_settings.ensure_defaults(
            [
                {
                    "key": NEW_USER_SETTING,
                    "value": {
                        "value": {
                            "role_code": ROLE_CODE,
                            "workspace_name": WORKSPACE_NAME,
                            "home_page": "/marketplace_app",
                        }
                    },
                    "description": (
                        "Параметры пользователя, создаваемого регистрацией: "
                        "role_code, workspace_name, home_page"
                    ),
                    "module": "registration",
                    "is_system": False,
                    "cache_ttl": 0,
                }
            ]
        )
