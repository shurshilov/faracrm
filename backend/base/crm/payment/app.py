# Copyright 2025 FARA CRM
# Payment module - application

from typing import TYPE_CHECKING

from backend.base.system.core.app import App
from backend.base.system.dotorm.dotorm.access import BYPASS_DOMAIN
from backend.base.crm.security.acl_post_init_mixin import ACL

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment


class PaymentApp(App):
    """
    Базовый модуль онлайн-оплаты с комиссией площадки.

    Провайдеры (T-Bank, Сбер, …) — отдельные модули, наследуют
    PaymentProviderBase и регистрируются через register_provider.
    """

    info = {
        "name": "Payment",
        "summary": "Online payments through external providers",
        "author": "FARA CRM",
        "category": "Sales",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["users", "security"],
        "post_init": True,
        # Платежи включаются осознанно (сами или как зависимость
        # маркетплейса), а не при первом старте.
        "auto_install": False,
    }

    # Свои платежи видны плательщику (правило ниже), управляет system_admin.
    BASE_USER_ACL = {"payment": ACL.READ_ONLY}
    ROLE_ACL = {"system_admin": {"payment": ACL.FULL}}

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        from backend.base.crm.payment.models.payment import (
            COMMISSION_SETTING,
        )

        await env.models.system_settings.ensure_defaults(
            [
                {
                    "key": COMMISSION_SETTING,
                    "value": {"value": 10},
                    "description": (
                        "Комиссия площадки с каждой оплаты, %. Остаётся "
                        "на счёте владельца терминала, остальное уходит "
                        "получателю."
                    ),
                    "module": "payment",
                    "is_system": False,
                    "cache_ttl": 0,
                }
            ]
        )
        await self._init_rules(env)

    async def _init_rules(self, env: "Environment"):
        """Плательщик видит свои платежи, system_admin — все."""
        from backend.base.crm.security.models.rules import Rule

        model = await env.models.model.search(
            filter=[("name", "=", "payment")], limit=1
        )
        system_admin = await env.models.role.search(
            filter=[("code", "=", "system_admin")], fields=["id"], limit=1
        )
        if not model or not system_admin:
            return

        rules = [
            (
                "Payment: payer sees own payments",
                None,
                [["payer_id", "=", "{{user_id}}"]],
                {"read": True},
            ),
            (
                "Payment: system admin sees all payments",
                system_admin[0],
                BYPASS_DOMAIN,
                {"read": True, "update": True},
            ),
        ]
        for name, role, domain, perms in rules:
            existing = await env.models.rule.search(
                filter=[("name", "=", name)], limit=1
            )
            if existing:
                continue
            await env.models.rule.create(
                payload=Rule(
                    name=name,
                    active=True,
                    model_id=model[0],
                    role_id=role,
                    domain=domain,
                    perm_create=perms.get("create", False),
                    perm_read=perms.get("read", False),
                    perm_update=perms.get("update", False),
                    perm_delete=perms.get("delete", False),
                )
            )
