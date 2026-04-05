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
    app_records = await env.models.app.search(
        filter=[("code", "=", app_code)],
        fields=["id"],
        limit=1,
    )
    if not app_records:
        return
    app_id = app_records[0].id

    # Получаем base_user
    base_user = await env.models.role.search(
        filter=[("code", "=", "base_user")],
        fields=["id"],
        limit=1,
    )
    if not base_user:
        return

    prev_code = "base_user"

    for code, name in roles_def:
        existing = await env.models.role.search(
            filter=[("code", "=", code)],
            fields=["id"],
            limit=1,
        )
        if existing:
            prev_code = code
            continue

        # based_role_ids: наследуем от предыдущей роли
        based_roles = []
        found = await env.models.role.search(
            filter=[("code", "=", prev_code)],
            fields=["id"],
            limit=1,
        )
        if found:
            based_roles.append(Role(id=found[0].id))

        role_payload = Role(
            code=code,
            name=name,
            app_id=AppModel(id=app_id),
            based_role_ids=based_roles,
        )
        await env.models.role.create(payload=role_payload)
        prev_code = code
