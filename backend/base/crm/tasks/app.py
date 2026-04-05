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
            "tasks",
            [
                ("project_user", "Проекты: пользователь"),
                ("project_manager", "Проекты: менеджер"),
                ("project_admin", "Проекты: администратор"),
            ],
        )

        # --- Начальные стадии задач ---
        for stage_data in INITIAL_TASK_STAGES:
            existing = await env.models.task_stage.search(
                filter=[("name", "=", stage_data["name"])],
            )
            if not existing:
                await env.models.task_stage.create(
                    payload=TaskStage(**stage_data),
                )

        # --- Начальные теги ---
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
