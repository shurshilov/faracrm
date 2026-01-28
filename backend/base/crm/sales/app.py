from fastapi import FastAPI
from backend.base.system.core.app import App
from backend.base.system.core.enviroment import Environment
from backend.base.crm.security.acl_post_init_mixin import ACL
from .models.sale_stage import SaleStage, INITIAL_SALE_STAGES


class SalesApp(App):
    """
    App for sales management
    """

    info = {
        "name": "Sales",
        "summary": "Module allow work with sales",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "sale": ACL.FULL,
        "sale_line": ACL.FULL,
        "sale_stage": ACL.FULL,
        "tax": ACL.FULL,
    }

    async def post_init(self, app: FastAPI):
        await super().post_init(app)
        env: Environment = app.state.env

        # Создание начальных стадий продаж
        db_session = env.apps.db.get_session()
        for stage_data in INITIAL_SALE_STAGES:
            existing_stages = await env.models.sale_stage.search(
                session=db_session, filter=[("name", "=", stage_data["name"])]
            )
            if not existing_stages:
                await env.models.sale_stage.create(
                    session=db_session,
                    payload=SaleStage(**stage_data),
                )
