from typing import TYPE_CHECKING

from fastapi import FastAPI

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL
from .models.company import Company

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment


class CompanyApp(App):
    """
    App company
    """

    info = {
        "name": "Company",
        "summary": "Module allow work with company",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "company": ACL.FULL,
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        # Дефолтная компания — создаётся при первом старте если в БД нет
        # ни одной записи. Используется как "текущая" для branding и
        # подобных глобальных настроек.
        existing = await env.models.company.search(limit=1)
        if not existing:
            await env.models.company.create(
                payload=Company(name="FARA CRM"),
            )
