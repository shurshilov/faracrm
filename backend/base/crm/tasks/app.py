from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL
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
        "task": ACL.FULL,
        "task_stage": ACL.FULL,
        "task_tag": ACL.FULL,
        "project": ACL.FULL,
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

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
