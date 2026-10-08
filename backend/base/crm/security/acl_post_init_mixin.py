"""
Права модулей: приложение объявляет ACL атрибутами класса, security
создаёт строки access_list при его post_init.

Использование:
    from backend.base.crm.security.acl_post_init_mixin import ACLPerms, ACL

    class LeadsApp(App):
        # Для роли base_user (по умолчанию)
        BASE_USER_ACL = {
            "lead": ACL.FULL,
            "lead_stage": ACLPerms(create=True, read=True, update=True, delete=False),
        }

        # Для других ролей
        ROLE_ACL = {
            "manager": {
                "lead": ACL.NO_DELETE,
            },
            "viewer": {
                "lead": ACL.READ_ONLY,
            },
        }

Ядро о правах не знает: базовый App.post_init зовёт хуки (App.hooks),
security подключает свой — ACLHook ниже (в security/app.py);
наследовать ничего не нужно.
Роли модуля создаются до super().post_init() — права ложатся в нём.
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.base.system.core.app import App, AppHook

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

log = logging.getLogger(__package__)


@dataclass(frozen=True)
class ACLPerms:
    """Права доступа для ACL."""

    create: bool = False
    read: bool = False
    update: bool = False
    delete: bool = False


class ACL:
    """Пресеты прав доступа."""

    FULL = ACLPerms(create=True, read=True, update=True, delete=True)
    READ_ONLY = ACLPerms(create=False, read=True, update=False, delete=False)
    NO_DELETE = ACLPerms(create=True, read=True, update=True, delete=False)
    NO_CREATE = ACLPerms(create=False, read=True, update=True, delete=True)
    NO_ACCESS = ACLPerms(create=False, read=False, update=False, delete=False)
    CREATE_READ = ACLPerms(create=True, read=True, update=False, delete=False)


class ACLHook(AppHook):
    """Права приложения — строки access_list при его post_init.

    BASE_USER_ACL: model_name -> ACLPerms для роли base_user;
    ROLE_ACL: role_code -> {model_name -> ACLPerms} для других ролей.
    """

    async def post_init(self, service: App, app: "FastAPI") -> None:
        """Создаёт ACL для всех ролей на модели этого модуля."""
        env: "Environment" = app.state.env
        # Инициализация для base_user
        base_user_acl = getattr(service, "BASE_USER_ACL", None)
        if base_user_acl:
            await self._init_acl_for_role(
                env, service, "base_user", base_user_acl
            )

        # Инициализация для других ролей
        role_acl = getattr(service, "ROLE_ACL", None) or {}
        for role_code, acl_config in role_acl.items():
            await self._init_acl_for_role(env, service, role_code, acl_config)

    async def _init_acl_for_role(
        self,
        env: "Environment",
        service: App,
        role_code: str,
        acl_config: dict[str, ACLPerms],
    ):
        """Создаёт ACL для указанной роли."""
        if not acl_config:
            return

        from backend.base.crm.security.models.acls import AccessList
        from backend.base.crm.security.models.roles import Role
        from backend.base.system.core.models.models import Model

        # Получаем роль
        role = await env.models.role.search_one(
            filter=[("code", "=", role_code)],
            fields=["id"],
        )
        if not role:
            # Не молчим: без роли ACL не создаётся, и модуль работает без
            # прав до следующего post_init. Роли модуля создаются
            # init_module_roles ДО super().post_init().
            log.warning(
                "ACL %s: role %r does not exist yet, ACL skipped",
                type(service).__name__,
                role_code,
            )
            return

        role_id = role.id

        # Получаем модели
        model_names = list(acl_config.keys())
        all_models = await env.models.model.search(
            filter=[("name", "in", model_names)],
            fields=["id", "name"],
        )
        model_by_name = {m.name: m.id for m in all_models}

        # Получаем существующие ACL для этой роли
        existing_acls = await env.models.access_list.search(
            filter=[("role_id", "=", role_id)],
            fields=["id", "model_id"],
        )
        existing_model_ids = {
            acl.model_id.id if acl.model_id else None for acl in existing_acls
        }

        # Создаём ACL
        for model_name, perms in acl_config.items():
            model_id = model_by_name.get(model_name)
            if not model_id:
                log.warning(
                    "ACL %s/%s: model %r is not registered, ACL skipped",
                    type(service).__name__,
                    role_code,
                    model_name,
                )
                continue
            if model_id in existing_model_ids:
                continue

            await env.models.access_list.create(
                payload=AccessList(
                    active=True,
                    name=f"{role_code}_{model_name}",
                    model_id=Model(id=model_id),
                    role_id=Role(id=role_id),
                    perm_create=perms.create,
                    perm_read=perms.read,
                    perm_update=perms.update,
                    perm_delete=perms.delete,
                )
            )
