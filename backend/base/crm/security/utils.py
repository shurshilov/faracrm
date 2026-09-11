"""
Утилита для создания ролей модулей.

Каждый модуль создаёт 3 роли с иерархией:
  {module}_user → {module}_manager → {module}_admin

Все роли наследуют base_user через based_role_ids.

Использование в app.py:
    from backend.base.crm.security.utils import init_module_roles

    async def post_init(self, app):
        env = app.state.env
        await init_module_roles(env, "partners", [
            ("partner_user",    "Партнёры: пользователь"),
            ("partner_manager", "Партнёры: менеджер"),
            ("partner_admin",   "Партнёры: администратор"),
        ])
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment


async def init_module_roles(
    env: "Environment",
    app_code: str,
    roles_def: list[tuple[str, str]],
) -> None:
    """
    Создать роли модуля с иерархией.

    Args:
        env: Environment
        app_code: Код приложения (должен существовать в таблице apps)
        roles_def: Список (code, name) в порядке иерархии.
                   Первая роль наследует base_user,
                   каждая следующая наследует предыдущую.

    Example:
        await init_module_roles(env, "partners", [
            ("partner_user",    "Партнёры: пользователь"),
            ("partner_manager", "Партнёры: менеджер"),
            ("partner_admin",   "Партнёры: администратор"),
        ])
    """
    from backend.base.crm.security.models.roles import Role
    from backend.base.crm.security.models.apps import App as AppModel

    # Получаем app_id
    app_record = await env.models.app.search_one(
        filter=[("code", "=", app_code)],
        fields=["id"],
    )
    if not app_record:
        return
    app_id = app_record.id

    # Получаем base_user
    base_user = await env.models.role.search_one(
        filter=[("code", "=", "base_user")],
        fields=["id"],
    )
    if not base_user:
        return

    prev_code = "base_user"

    for code, name in roles_def:
        existing = await env.models.role.search_one(
            filter=[("code", "=", code)],
            fields=["id"],
        )
        if existing:
            prev_code = code
            continue

        # based_role_ids: наследуем от предыдущей роли
        based_role_id = None
        found = await env.models.role.search_one(
            filter=[("code", "=", prev_code)],
            fields=["id"],
        )
        if found:
            based_role_id = found.id

        role_payload = Role(
            code=code,
            name=name,
            app_id=AppModel(id=app_id),
        )
        new_role_id = await env.models.role.create(payload=role_payload)

        # ВАЖНО: m2m (based_role_ids) сохраняются ТОЛЬКО через update(),
        # а не через create(). И link_many2many ожидает int id, а не объекты.
        # См. dotorm/orm/mixins/primary.py:create — only_store=True пропускает m2m.
        if based_role_id is not None:
            new_role = await env.models.role.get(new_role_id)
            await new_role.update(
                payload=Role(based_role_ids={"selected": [based_role_id]})
            )

        prev_code = code
