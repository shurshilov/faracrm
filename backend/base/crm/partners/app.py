from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL
from .models.contact_type import ContactType, INITIAL_CONTACT_TYPES


class PartnersApp(App):
    """
    App auth
    """

    info = {
        "name": "Partners",
        "summary": "Module allow work with partners",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "partner": ACL.FULL,
        "contact": ACL.FULL,
        "contact_type": ACL.FULL,
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        # Начальные типы контактов
        for type_data in INITIAL_CONTACT_TYPES:
            existing = await env.models.contact_type.search(
                filter=[("name", "=", type_data["name"])],
            )
            if not existing:
                await env.models.contact_type.create(
                    payload=ContactType(**type_data),
                )
