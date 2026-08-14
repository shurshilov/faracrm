# Copyright 2025 FARA CRM
# Chat Phone Asterisk module - application configuration

import asyncio
import logging
from typing import TYPE_CHECKING

from backend.base.system.core.service import Service
from backend.base.crm.security.acl_post_init_mixin import ACL

if TYPE_CHECKING:
    from fastapi import FastAPI
    from backend.base.system.core.enviroment import Environment

logger = logging.getLogger(__name__)

# Класс advisory-lock для ARI-слушателей Asterisk (int4). Гарантирует, что при
# нескольких uvicorn-воркерах WS-коннект к ARI на данный коннектор держит ровно
# один воркер (objid = connector_id). Аналог cron/locking.py.
ASTERISK_ARI_LOCK_CLASS = 0x4153  # 'AS'


class ChatPhoneAsteriskApp(Service):
    """
    Интеграция с Asterisk / FreePBX. Два режима транспорта (connector.agent_mode):

    - remote (default): внешний Asterisk-agent (FastAPI рядом с Asterisk) шлёт
      ARI-события на универсальный webhook FARA; историю/записи FARA тянет из
      REST API агента по HTTP Basic-auth.
    - local: встроенный режим на базе пакета ``asterisk_agent`` — CDR читается
      прямым SQL из БД Asterisk, а ARI-события слушаются in-process постоянной
      фоновой задачей (по одной на local-коннектор), которая на каждое событие
      зовёт strategy.handle_webhook напрямую (без HTTP).

    Сервис (startup/shutdown) поднимает и гасит WS-слушатели local-коннекторов.
    """

    info = {
        "name": "Chat Phone Asterisk",
        "summary": "Asterisk / FreePBX telephony integration",
        "author": "FARA CRM",
        "category": "Chat",
        "version": "1.1.0",
        "license": "FARA CRM License v1.0",
        "depends": ["chat_phone", "cron"],
        "sequence": 118,
        "post_init": True,
        "service": True,
    }

    # asterisk_log — журнал телефонии (экран «События»): правит система (запись
    # ведёт слушатель), юзерам — чтение. Без ACL модель default-deny (экран пуст).
    BASE_USER_ACL = {
        "asterisk_log": ACL.READ_ONLY,
    }
    ROLE_ACL = {
        "system_admin": {
            "asterisk_log": ACL.FULL,
        },
    }

    def __init__(self):
        super().__init__()

        from backend.base.crm.chat.strategies import register_strategy
        from backend.base.crm.chat_phone_asterisk.strategies import (
            AsteriskPhoneStrategy,
        )

        register_strategy(AsteriskPhoneStrategy)

        # connector_id -> asyncio.Task (ARI WS-слушатель local-режима)
        self._listener_tasks: dict[int, asyncio.Task] = {}

    async def post_init(self, app: "FastAPI"):
        """
        Зарегистрировать cron периодического импорта истории звонков.

        По умолчанию неактивен — включается вручную в списке cron-задач.
        Работает и для remote, и для local (fetch_call_history идёт через источник).
        """
        await super().post_init(app)
        env: "Environment" = app.state.env

        await env.models.cron_job.create_or_update(
            env=env,
            name="Asterisk: Fetch call history",
            code="""
from backend.base.crm.chat_phone_asterisk.strategies import AsteriskPhoneStrategy
result = await AsteriskPhoneStrategy.cron_fetch_call_history(env)
""",
            interval_number=2,
            interval_type="minutes",
            active=False,
            priority=20,
        )

        await env.models.cron_job.create_or_update(
            env=env,
            name="Asterisk: Sync numbers",
            code="""
from backend.base.crm.chat_phone_asterisk.strategies import AsteriskPhoneStrategy
result = await AsteriskPhoneStrategy.cron_sync_numbers(env)
""",
            interval_number=1,
            interval_type="days",
            active=False,
            priority=20,
        )

    # ==================== жизненный цикл in-process ARI WS ====================

    async def startup(self, app: "FastAPI") -> None:
        """Поднять WS-слушатели для local-коннекторов с включённым автозапуском."""
        env: "Environment" = app.state.env
        try:
            connectors = await env.models.chat_connector.search(
                filter=[
                    ("type", "=", "phone_asterisk"),
                    ("active", "=", True),
                    ("agent_mode", "=", "local"),
                    ("asterisk_ari_autostart", "=", True),
                ],
                fields=[
                    "id",
                    "name",
                    "asterisk_ari_url",
                    "asterisk_ari_wss",
                    "asterisk_ari_login",
                    "asterisk_ari_password",
                ],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[phone_asterisk] listener startup query failed: %s", exc
            )
            return

        # На старте — advisory-lock (dedup между воркерами), затем спавн задачи.
        for connector in connectors:
            if not await self._acquire_lock(env, connector.id):
                logger.info(
                    "[phone_asterisk] connector %s: ARI listener held by another worker",
                    connector.id,
                )
                continue
            self._spawn_listener(env, connector)

    def _spawn_listener(self, env: "Environment", connector) -> bool:
        """
        Создать задачу-слушатель для коннектора (advisory-lock'ом ведает startup).
        Гвард: нужны ARI url/wss. Идемпотентно (уже запущен → True).
        """
        task = self._listener_tasks.get(connector.id)
        if task and not task.done():
            return True
        if not (connector.asterisk_ari_url and connector.asterisk_ari_wss):
            logger.info(
                "[phone_asterisk] connector %s (%s): ARI не настроен (url/wss пусты) "
                "— слушатель не запущен",
                connector.id,
                connector.name,
            )
            return False
        task = asyncio.create_task(
            self._run_listener(env, connector),
            name=f"asterisk_ari_listener_{connector.id}",
        )
        self._listener_tasks[connector.id] = task
        logger.info(
            "[phone_asterisk] started ARI listener for connector %s (%s)",
            connector.id,
            connector.name,
        )
        return True

    async def ensure_listener(self, env: "Environment", connector) -> bool:
        """
        Запустить слушатель СЕЙЧАС (по свичу «Автозапуск»). Без advisory-lock —
        стартуем на текущем воркере. True, если запущен (или уже работает).
        """
        return self._spawn_listener(env, connector)

    async def stop_listener(self, connector_id: int) -> None:
        """Остановить слушатель коннектора (выключение автозапуска)."""
        task = self._listener_tasks.pop(connector_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[phone_asterisk] stop_listener error (connector %s): %s",
                    connector_id,
                    exc,
                )

    async def shutdown(self, app: "FastAPI") -> None:
        """Погасить все WS-слушатели."""
        tasks = list(self._listener_tasks.values())
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[phone_asterisk] listener shutdown error: %s", exc
                )
        self._listener_tasks.clear()

    async def _run_listener(self, env: "Environment", connector) -> None:
        """Supervised WS-слушатель одного коннектора (reconnect внутри пакета)."""
        from backend.base.crm.chat_phone_asterisk.strategies.sources import (
            LocalAgentSource,
        )

        try:
            ws = LocalAgentSource.build_ws(
                connector, self._make_dispatch(env, connector.id)
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[phone_asterisk] cannot build ARI client for connector %s: %s",
                connector.id,
                exc,
            )
            return
        await ws.run_forever()

    def _make_dispatch(self, env: "Environment", connector_id: int):
        """
        Колбэк на ARI-событие: воспроизводит тело webhook-роута (без HTTP-парсинга).
        Внимание: access-сессия — ContextVar с default-deny, поэтому её нужно
        установить в самом колбэке (в HTTP её ставит Depends, здесь его нет).
        """

        async def dispatch(event: dict) -> None:
            from backend.base.crm.security.models.sessions import SystemSession
            from backend.base.crm.users.models.users import SYSTEM_USER_ID
            from backend.base.system.dotorm.dotorm.access import (
                clear_access_session,
                set_access_session,
            )

            set_access_session(SystemSession(user_id=SYSTEM_USER_ID))
            try:
                connectors = await env.models.chat_connector.search(
                    filter=[("id", "=", connector_id), ("active", "=", True)],
                    fields_nested={
                        "contact_type_id": ["id", "name", "is_phone_format"]
                    },
                    limit=1,
                )
                if connectors:
                    await connectors[0].strategy.handle_webhook(
                        connector=connectors[0], payload=event, env=env
                    )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "[phone_asterisk] ARI dispatch failed (connector %s): %s",
                    connector_id,
                    exc,
                    exc_info=True,
                )
            finally:
                clear_access_session()

        return dispatch

    async def _acquire_lock(
        self, env: "Environment", connector_id: int
    ) -> bool:
        """
        Неблокирующий pg_try_advisory_lock(class, connector_id): True — этот воркер
        держит слушатель, False — держит другой. При ошибке не блокируем запуск.
        """
        try:
            pool = env.apps.db.fara
            async with pool.acquire() as conn:
                return bool(
                    await conn.fetchval(
                        "SELECT pg_try_advisory_lock($1, $2)",
                        ASTERISK_ARI_LOCK_CLASS,
                        int(connector_id),
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[phone_asterisk] advisory lock failed for connector %s: %s",
                connector_id,
                exc,
            )
            return True
