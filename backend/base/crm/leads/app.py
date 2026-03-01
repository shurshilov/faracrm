from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL
from .models.lead_stage import LeadStage, INITIAL_LEAD_STAGES


class LeadsApp(App):
    """
    App for leads/CRM management
    """

    info = {
        "name": "Leads",
        "summary": "Module allow work with leads",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "lead": ACL.FULL,
        "lead_stage": ACL.FULL,
        "team_crm": ACL.FULL,
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        # Создание начальных стадий лидов
        for stage_data in INITIAL_LEAD_STAGES:
            existing_stages = await env.models.lead_stage.search(
                filter=[("name", "=", stage_data["name"])]
            )
            if not existing_stages:
                await env.models.lead_stage.create(
                    payload=LeadStage(**stage_data),
                )
