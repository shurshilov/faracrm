"""
Mixin для инициализации ACL в post_init модулей.

Использование:
    from backend.base.crm.security.acl_post_init_mixin import ACLPostInitMixin, ACLPerms, ACL

    class LeadsApp(ACLPostInitMixin, App):
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

        async def post_init(self, app: FastAPI):
            await super().post_init(app)
            await self._init_acl(app.state.env)
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment


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


class ACLPostInitMixin:
    """Mixin для создания ACL записей в post_init."""

    # ACL для роли base_user (по умолчанию)
    BASE_USER_ACL: dict[str, ACLPerms] = {}

    # ACL для других ролей
    # Формат: role_code -> {model_name -> ACLPerms}
    ROLE_ACL: dict[str, dict[str, ACLPerms]] = {}

    async def _init_acl(self, env: "Environment"):
        """Создаёт ACL для всех ролей на модели этого модуля."""
        # Инициализация для base_user
        if self.BASE_USER_ACL:
            await self._init_acl_for_role(env, "base_user", self.BASE_USER_ACL)

        # Инициализация для других ролей
        for role_code, acl_config in self.ROLE_ACL.items():
            await self._init_acl_for_role(env, role_code, acl_config)

    async def _init_acl_for_role(
        self,
        env: "Environment",
        role_code: str,
        acl_config: dict[str, ACLPerms],
    ):
        """Создаёт ACL для указанной роли."""
        if not acl_config:
            return

        from backend.base.crm.security.models.acls import AccessList
        from backend.base.crm.security.models.models import Model
        from backend.base.crm.security.models.roles import Role

        # Получаем роль
        role = await env.models.role.search(
            filter=[("code", "=", role_code)],
            fields=["id"],
            limit=1,
        )
        if not role:
            return

        role_id = role[0].id

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
            if not model_id or model_id in existing_model_ids:
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
