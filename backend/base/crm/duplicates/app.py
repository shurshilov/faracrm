# Copyright 2025 FARA CRM
# Duplicates module - application

from typing import TYPE_CHECKING

from backend.base.system.core.app import App
from .models import (
    ContactDuplicatesMixin,
    DuplicateMode,
    PartnerDuplicatesMixin,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment


class DuplicatesApp(App):
    """
    Контроль дубликатов партнёров и контактов. Правила навешаны на модели
    через @extend (models/duplicates_ext.py), режимы — системные настройки
    constrains.*; своих моделей и роутов нет. Ставится по умолчанию; если
    снять на странице приложений, правила молчат: они проверяют флаг
    «установлено» (env.is_installed), потому что @extend навешивается при
    импорте независимо от установки.
    """

    info = {
        "name": "Duplicates",
        "summary": "Контроль дубликатов партнёров и контактов: имя, ИНН+КПП, "
        "значение контакта",
        "author": "FARA CRM",
        "category": "Base",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["partners", "contract"],
        "post_init": True,
        "auto_install": True,
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        env: "Environment" = app.state.env

        # Дефолт: block только у контакта партнёра (номер у двух партнёров
        # ломает привязку входящих: find_for_webhook берёт первого
        # попавшегося). Остальные правила выключены (пусто) — включаются
        # в системных настройках значением warn или block.
        rules = [
            (
                PartnerDuplicatesMixin.DUPLICATE_NAME_KEY,
                None,
                "Контроль дубликатов партнёров по имени",
            ),
            (
                PartnerDuplicatesMixin.DUPLICATE_VAT_KEY,
                None,
                "Контроль дубликатов партнёров по ИНН и КПП",
            ),
            (
                ContactDuplicatesMixin.DUPLICATE_KEYS["partner_id"],
                DuplicateMode.BLOCK,
                "Контроль дубликатов контактов партнёров по значению "
                "(телефон, email, id мессенджера)",
            ),
            (
                ContactDuplicatesMixin.DUPLICATE_KEYS["user_id"],
                None,
                "Контроль дубликатов контактов сотрудников по значению "
                "(номер, SIP-extension)",
            ),
        ]
        await env.models.system_settings.ensure_defaults(
            [
                {
                    "key": key,
                    "value": {"value": default.value if default else None},
                    "description": f"{text}: warn (в лог) / block, пусто — "
                    "выключено. Кеш навсегда — после смены нужен рестарт",
                    "module": "constrains",
                    "is_system": True,
                    "cache_ttl": -1,
                }
                for key, default, text in rules
            ]
        )
