# Copyright 2025 FARA CRM
# Chat Phone module - application configuration

import json
from typing import TYPE_CHECKING

from backend.base.system.core.app import App
from backend.base.crm.security.acl_post_init_mixin import ACL

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

# Фильтры периода для экрана «Звонки»: обычные общие saved_filters на модель
# call, «Сегодня» — по умолчанию. Границу подставляет фронт при применении
# фильтра (плейсхолдер, как {{user_id}} у «Моих файлов»), поэтому одна запись
# в БД работает для всех пользователей и не устаревает.
CALL_PERIOD_FILTERS = [
    ("Сегодня", "{{today}}", True),
    ("Эта неделя", "{{week_start}}", False),
    ("Этот месяц", "{{month_start}}", False),
    ("Этот квартал", "{{quarter_start}}", False),
    ("Этот год", "{{year_start}}", False),
]

# Фоновые задачи, одинаковые для всех телефонных провайдеров: бэкофилл истории
# звонков и синхронизация номеров. Реализация — chat_phone/cron.py.
# Интервал заметно меньше окна истории (HISTORY_WINDOW_MINUTES): перекрытие —
# страховка от задержки записи у провайдера и от пропущенных тиков. Каждая
# запись в окне прогоняется по разу на тик, поэтому 2 минуты при часовом окне
# давали бы ~30 прогонов одного и того же.
PHONE_CRONS = [
    ("Fetch call history", "fetch_call_history", 15, "minutes"),
    ("Sync numbers", "sync_numbers", 1, "days"),
]


async def register_phone_crons(
    env: "Environment",
    label: str,
    strategy_type: str,
) -> None:
    """
    Зарегистрировать cron-задачи телефонии для провайдера (идемпотентно).

    По умолчанию НЕАКТИВНЫ — включаются вручную в списке cron-задач.
    """
    for suffix, func, interval_number, interval_type in PHONE_CRONS:
        # cron вызывает метод модели phone_number (не произвольный код).
        # Провайдер передаётся в kwargs задачи (strategy_type). Определение
        # (метод/kwargs) синхронизируется create_or_update и на старых базах.
        await env.models.cron_job.create_or_update(
            env=env,
            name=f"{label}: {suffix}",
            model_name="phone_number",
            method_name=f"cron_{func}",
            kwargs=json.dumps({"strategy_type": strategy_type}),
            interval_number=interval_number,
            interval_type=interval_type,
            active=False,
            priority=20,
        )


class ChatPhoneApp(App):
    """
    Базовый модуль телефонии для чатов.

    Добавляет:
    - Базовую стратегию для телефонных коннекторов

    Конкретные провайдеры (Sipuni, Mango, etc.) реализуются
    в отдельных модулях, наследуя PhoneStrategyBase.
    """

    info = {
        "ui_menu": True,
        "ui_menu_name": "telephony",
        "name": "Chat Phone",
        "summary": "Base telephony integration for chat module",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.0.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat"],
        "sequence": 115,
        "post_init": True,
    }

    # phone_number справочник номеров телефонии: правит админ, юзерам чтение
    BASE_USER_ACL = {
        "phone_number": ACL.READ_ONLY,
        "call": ACL.READ_ONLY,
    }
    ROLE_ACL = {
        "system_admin": {
            "phone_number": ACL.FULL,
            "call": ACL.FULL,
        },
    }

    async def post_init(self, app: "FastAPI"):
        await super().post_init(app)
        await self._init_call_period_filters(app.state.env)

    async def _init_call_period_filters(self, env: "Environment"):
        """Создать фильтры периода для «Звонков» (идемпотентно)."""
        from backend.base.system.saved_filters.models.saved_filter import (
            SavedFilter,
        )

        for name, placeholder, is_default in CALL_PERIOD_FILTERS:
            filter_data = json.dumps([["started_at", ">=", placeholder]])
            existing = await env.models.saved_filter.search(
                filter=[
                    ("model_name", "=", "call"),
                    ("name", "=", name),
                    ("is_global", "=", True),
                ],
                limit=1,
            )
            if existing:
                if existing[0].filter_data == filter_data:
                    continue
                await existing[0].delete()

            await env.models.saved_filter.create(
                payload=SavedFilter(
                    name=name,
                    model_name="call",
                    filter_data=filter_data,
                    user_id=None,
                    is_global=True,
                    is_default=is_default,
                ),
            )
