from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL
from .models.sale_stage import SaleStage, INITIAL_SALE_STAGES


class SalesApp(App):
    """
    App for sales management.

    Роли:
    ┌──────────────────────────┬───────────────────────────────────────────┐
    │ Код роли                 │ Описание                                  │
    ├──────────────────────────┼───────────────────────────────────────────┤
    │ sale_salesman            │ Продавец — видит только свои заказы       │
    │ sale_salesman_all        │ Руководитель — видит все заказы           │
    │ sale_manager             │ Администратор — полный доступ + настройки │
    └──────────────────────────┴───────────────────────────────────────────┘

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
        "sale_stage": ACL.READ_ONLY,
        "tax": ACL.READ_ONLY,
    }

    ROLE_ACL = {
        # Продавец: полный CRUD включая удаление своих заказов
        "sale_salesman": {
            "sale": ACL.FULL,
            "sale_line": ACL.FULL,
            "sale_stage": ACL.READ_ONLY,
            "tax": ACL.READ_ONLY,
        },
        # Руководитель: полный CRUD включая удаление
        "sale_salesman_all": {
            "sale": ACL.FULL,
            "sale_line": ACL.FULL,
            "sale_stage": ACL.READ_ONLY,
            "tax": ACL.READ_ONLY,
        },
        # Администратор: полный доступ + управление стадиями и налогами
        "sale_manager": {
            "sale": ACL.FULL,
            "sale_line": ACL.FULL,
            "sale_stage": ACL.FULL,
            "tax": ACL.FULL,
        },
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        # 1. Начальные стадии продаж
        await self._init_sale_stages(env)

        # 2. Роли модуля (иерархия: salesman → salesman_all → manager)
        await self._init_sale_roles(env)

        # 3. ACL для ролей модуля
        await self._init_acl(env)

        # 4. Row-level rules
        await self._init_sale_rules(env)

    async def _init_sale_stages(self, env: "Environment"):
        """Создаёт начальные стадии продаж."""

        for stage_data in INITIAL_SALE_STAGES:
            existing = await env.models.sale_stage.search(
                filter=[("name", "=", stage_data["name"])]
            )
            if not existing:
                await env.models.sale_stage.create(
                    payload=SaleStage(**stage_data),
                )

    async def _init_sale_roles(self, env: "Environment"):
        """
        Создаёт три роли модуля продаж с иерархией через based_role_ids.
        """

        from backend.base.crm.security.models.roles import Role
        from backend.base.crm.security.models.apps import App as AppModel

        # Получаем app_id для sales
        sales_app = await env.models.app.search(
            filter=[("code", "=", "sales")],
            fields=["id"],
            limit=1,
        )
        if not sales_app:
            return
        app_id = sales_app[0].id

        # Получаем base_user
        base_user = await env.models.role.search(
            filter=[("code", "=", "base_user")],
            fields=["id"],
            limit=1,
        )

        if not base_user:
            return

        base_user_id = base_user[0].id

        # Описания ролей: (code, name, based_on_codes)
        roles_def = [
            (
                "sale_salesman",
                "Продавец",
                ["base_user"] if base_user_id else [],
            ),
            (
                "sale_salesman_all",
                "Руководитель продаж",
                ["sale_salesman"],
            ),
            (
                "sale_manager",
                "Администратор продаж",
                ["sale_salesman_all"],
            ),
        ]

        for code, name, based_codes in roles_def:
            existing = await env.models.role.search(
                filter=[("code", "=", code)],
                fields=["id"],
                limit=1,
            )
            if existing:
                continue

            # Собираем based_role_ids
            based_roles = []
            for based_code in based_codes:
                found = await env.models.role.search(
                    filter=[("code", "=", based_code)],
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

    async def _init_sale_rules(self, env: "Environment"):
        """
        Создаёт правила доступа к записям (row-level security).
        """

        from backend.base.crm.security.models.rules import Rule

        # Получаем модели
        sale_model = await env.models.model.search(
            filter=[("name", "=", "sale")], limit=1
        )
        sale_line_model = await env.models.model.search(
            filter=[("name", "=", "sale_line")], limit=1
        )
        if not sale_model or not sale_line_model:
            return

        sale_model_rec = sale_model[0]
        sale_line_model_rec = sale_line_model[0]

        # Получаем роли
        role_salesman = await env.models.role.search(
            filter=[("code", "=", "sale_salesman")], limit=1
        )
        role_all = await env.models.role.search(
            filter=[("code", "=", "sale_salesman_all")], limit=1
        )
        if not role_salesman or not role_all:
            return

        rules_to_create = [
            {
                "name": "Заказы на продажу: только свои",
                "model_id": sale_model_rec,
                "role_id": role_salesman[0],
                # OR: назначен я, или ответственный не указан
                "domain": [
                    ["user_id", "=", "{{user_id}}"],
                    "or",
                    ["user_id", "=", None],
                ],
                "perm_read": True,
                "perm_create": True,
                "perm_update": True,
                "perm_delete": True,
            },
            {
                "name": "Заказы на продажу: все",
                "model_id": sale_model_rec,
                "role_id": role_all[0],
                "domain": [["id", "!=", None]],  # 1=1
                "perm_read": True,
                "perm_create": True,
                "perm_update": True,
                "perm_delete": True,
            },
            {
                "name": "Строки заказов: только свои",
                "model_id": sale_line_model_rec,
                "role_id": role_salesman[0],
                # Фильтрация через связанное поле sale_id.user_id
                "domain": [
                    ["sale_id.user_id", "=", "{{user_id}}"],
                    "or",
                    ["sale_id.user_id", "=", None],
                ],
                "perm_read": True,
                "perm_create": True,
                "perm_update": True,
                "perm_delete": True,
            },
            {
                "name": "Строки заказов: все",
                "model_id": sale_line_model_rec,
                "role_id": role_all[0],
                "domain": [["id", "!=", None]],  # 1=1
                "perm_read": True,
                "perm_create": True,
                "perm_update": True,
                "perm_delete": True,
            },
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
                    perm_create=rule_data["perm_create"],
                    perm_read=rule_data["perm_read"],
                    perm_update=rule_data["perm_update"],
                    perm_delete=rule_data["perm_delete"],
                )
            )
