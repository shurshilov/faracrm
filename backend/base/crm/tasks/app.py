from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL
from backend.base.crm.security.utils import init_module_roles
from .models.task_stage import TaskStage, INITIAL_TASK_STAGES
from .models.task_tag import TaskTag, INITIAL_TASK_TAGS


class TasksApp(App):
    """
    App for tasks & projects management.

    Роли:
    ┌──────────────────┬─────────────────────────────────────────────────┐
    │ Код роли         │ Описание                                        │
    ├──────────────────┼─────────────────────────────────────────────────┤
    │ project_user     │ Пользователь — видит только проекты где он      │
    │                  │ manager_id или в member_ids. Задачи —           │
    │                  │ только в таких проектах.                        │
    │ project_manager  │ Менеджер — видит ВСЕ проекты и задачи           │
    │                  │ (row-level security снят).                      │
    │ project_admin    │ Администратор — видит всё и управляет           │
    │                  │ стадиями / тегами.                              │
    └──────────────────┴─────────────────────────────────────────────────┘
    """

    info = {
        "name": "Tasks",
        "summary": "Project and task management module",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "task_stage": ACL.READ_ONLY,
        "task_tag": ACL.READ_ONLY,
    }

    ROLE_ACL = {
        "project_user": {
            "task": ACL.FULL,
            "project": ACL.FULL,
            "task_stage": ACL.READ_ONLY,
            "task_tag": ACL.READ_ONLY,
        },
        "project_manager": {
            "task": ACL.FULL,
            "project": ACL.FULL,
            "task_stage": ACL.READ_ONLY,
            "task_tag": ACL.READ_ONLY,
        },
        "project_admin": {
            "task": ACL.FULL,
            "project": ACL.FULL,
            "task_stage": ACL.FULL,
            "task_tag": ACL.FULL,
        },
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        # Роли модуля
        await init_module_roles(
            env,
            "task",
            [
                ("project_user", "Проекты: пользователь"),
                ("project_manager", "Проекты: менеджер"),
                ("project_admin", "Проекты: администратор"),
            ],
        )

        # Начальные стадии задач
        for stage_data in INITIAL_TASK_STAGES:
            existing = await env.models.task_stage.search(
                filter=[("name", "=", stage_data["name"])],
            )
            if not existing:
                await env.models.task_stage.create(
                    payload=TaskStage(**stage_data),
                )

        # Начальные теги
        for tag_data in INITIAL_TASK_TAGS:
            existing = await env.models.task_tag.search(
                filter=[("name", "=", tag_data["name"])],
            )
            if not existing:
                await env.models.task_tag.create(
                    payload=TaskTag(
                        name=tag_data["name"], color=tag_data["color"]
                    ),
                )

        # Row-level rules: membership-based access к проектам и задачам
        await self._init_task_rules(env)

    async def _init_task_rules(self, env: "Environment"):
        """
        Membership-based row-level security.

        - project_user:    видит проекты где manager_id=я ИЛИ я в member_ids.
                           Задачи — по проекту, где я участник/менеджер.
        - project_manager: видит ВСЕ проекты и задачи (не ограничен членством).
        - project_admin:   видит всё (+ может менять настройки через ACL).

        ВАЖНО: DotORM rules объединяются OR между правилами одной роли
        на одну модель. Поэтому membership-domain оформлен одним выражением.

        Иерархия based_role_ids уже расширяет видимость:
        - project_manager через based получает rule от project_user
          (свои/участник) И собственное «всё» → итого OR = всё.
        - project_admin аналогично — наследует от manager, получает «всё».
        """
        from backend.base.crm.security.models.rules import Rule

        project_model = await env.models.model.search(
            filter=[("name", "=", "project")], limit=1
        )
        task_model = await env.models.model.search(
            filter=[("name", "=", "task")], limit=1
        )
        if not project_model or not task_model:
            return
        project_model_rec = project_model[0]
        task_model_rec = task_model[0]

        role_user = await env.models.role.search(
            filter=[("code", "=", "project_user")], limit=1
        )
        role_manager = await env.models.role.search(
            filter=[("code", "=", "project_manager")], limit=1
        )
        role_admin = await env.models.role.search(
            filter=[("code", "=", "project_admin")], limit=1
        )
        if not role_user or not role_manager or not role_admin:
            return

        # Domain для project_user: (manager_id = я) OR (я participant в project_member)
        # Используем @is_member оператор который генерирует SQL-subquery
        # вместо обращения к One2many (которое не работает на уровне SQL).
        project_member_domain = [
            ["manager_id", "=", "{{user_id}}"],
            "or",
            ["@is_member", "id", "project_member", "project_id"],
        ]
        # Для тасков — через FK на project_id, а проверка project'а
        # делается через @has_parent_access (рекурсивно применит правила
        # project_id, в т.ч. @is_member выше).
        task_member_domain = [
            ["@has_parent_access", "project", "project_id"],
        ]
        # Широкий domain — «все записи» (для manager/admin)
        all_domain = [["id", "!=", None]]

        rules_to_create = [
            {
                "name": "Проекты: мои или где я участник",
                "model_id": project_model_rec,
                "role_id": role_user[0],
                "domain": project_member_domain,
            },
            {
                "name": "Проекты: все (менеджер)",
                "model_id": project_model_rec,
                "role_id": role_manager[0],
                "domain": all_domain,
            },
            # {
            #     "name": "Проекты: все (админ)",
            #     "model_id": project_model_rec,
            #     "role_id": role_admin[0],
            #     "domain": all_domain,
            # },
            {
                "name": "Задачи: в проектах где я участник",
                "model_id": task_model_rec,
                "role_id": role_user[0],
                "domain": task_member_domain,
            },
            {
                "name": "Задачи: все (менеджер)",
                "model_id": task_model_rec,
                "role_id": role_manager[0],
                "domain": all_domain,
            },
            # {
            #     "name": "Задачи: все (админ)",
            #     "model_id": task_model_rec,
            #     "role_id": role_admin[0],
            #     "domain": all_domain,
            # },
        ]

        for rule_data in rules_to_create:
            existing = await env.models.rule.search(
                filter=[("name", "=", rule_data["name"])],
                limit=1,
            )
            if existing:
                continue

            await env.models.rule.create(
                payload=Rule(
                    name=rule_data["name"],
                    active=True,
                    model_id=rule_data["model_id"],
                    role_id=rule_data["role_id"],
                    domain=rule_data["domain"],
                    perm_create=True,
                    perm_read=True,
                    perm_update=True,
                    perm_delete=True,
                )
            )
