from typing import TYPE_CHECKING

from fastapi import FastAPI

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL
from backend.base.crm.security.utils import init_module_roles
from .models.uom import Uom

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment


class ProductsApp(App):
    """
    App auth
    """

    info = {
        "name": "Products",
        "summary": "Module allow work with products",
        "author": "FARA ERP",
        "category": "Base",
        "version": "1.0.0.0",
        "license": "FARA CRM License v1.0",
        "post_init": True,
        "depends": ["security"],
    }

    BASE_USER_ACL = {
        "product": ACL.FULL,
        "category": ACL.FULL,
        "uom": ACL.FULL,
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        await init_module_roles(
            env,
            "products",
            [
                ("stock_user", "Склад: пользователь"),
                ("stock_manager", "Склад: менеджер"),
                ("stock_admin", "Склад: администратор"),
            ],
        )

        initial_product_uom = [
            {"name": "штуки"},
            {"name": "килограммы"},
            {"name": "метры"},
            {"name": "литры"},
            {"name": "часы"},
        ]
        # начальные единицы измерения
        for uom_data in initial_product_uom:
            existing = await env.models.uom.search(
                filter=[("name", "=", uom_data["name"])],
            )
            if not existing:
                await env.models.uom.create(
                    payload=Uom(name=uom_data["name"]),
                )
