# Copyright 2025 FARA CRM
# Chat Phone module - base phone strategy

import logging
from typing import TYPE_CHECKING, Any, Tuple

from backend.base.crm.chat.strategies.strategy import ChatStrategyBase

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.project_setup import ChatConnector
    from backend.base.crm.partners.models.contact import Contact
    from .adapter import PhoneMessageAdapter

logger = logging.getLogger(__name__)


class PhoneStrategyBase(ChatStrategyBase):
    """
    Базовая стратегия телефонных коннекторов.

    Звонок — САМОСТОЯТЕЛЬНАЯ сущность (модель call), а НЕ сообщение. handle_webhook
    парсит CDR адаптером и прогоняет через IncomingCallPipeline (наследник
    message-пайплайна: reuse резолва клиент→партнёр→лид, но пишет строку call
    upsert-ом по uniqueid, без чата/сообщения). Экран «Звонки» читает call
    напрямую; в историю чата звонки подмешиваются на чтении (call_external).

    Провайдеры (Sipuni, MegaFon, Asterisk) реализуют:
    - create_message_adapter() — парсинг формата провайдера (PhoneMessageAdapter);
    - get_or_generate_token() / set_webhook() / unset_webhook();
    - _download_call_record() — скачивание записи (опционально, дефолт по URL);
    - chat_send_message() — инициация исходящего звонка (опционально).

    Событие звонка (ringing/answered/ended) определяется адаптером (event_type).
    """

    # Телефонии outbox-аккаунт не нужен; запись качаем сами (content).
    requires_outbox_account = False
    attachments_source = "content"

    async def handle_webhook(
        self,
        connector: "ChatConnector",
        payload: dict,
        env: "Environment",
        notify: bool = True,
        generate_lead: bool = True,
    ) -> Any:
        """
        Один webhook-эвент звонка → расширенный пайплайн.

        Дедуп по message_id НЕ делаем (в отличие от мессенджеров): у звонка
        несколько событий с ОДНИМ call_id, и пайплайн сам решает create/update.

        notify/generate_lead прокидываем в пайплайн: импорт истории из CDR может
        отключить живой попап и/или лидогенерацию (по умолчанию — обычный режим).
        """
        try:
            adapter: "PhoneMessageAdapter" = self.create_message_adapter(
                connector, payload
            )  # type: ignore
            if adapter.should_skip:
                return {"ok": True}
            # Адаптер подгружает номера сотрудников (для резолва внутр./клиент).
            await adapter.cache_numbers(env)
            # Звонок пишется в НЕЗАВИСИМУЮ таблицу call (не chat_message) через
            # call-пайплайн: reuse резолва клиент→партнёр→лид из message-пайплайна.
            from .pipeline_incoming_call import IncomingCallPipeline

            async with env.apps.db.get_transaction():
                await IncomingCallPipeline(
                    self, env, connector, adapter, generate_lead=generate_lead
                ).run()
            return {"ok": True}
        except Exception as e:  # noqa: BLE001
            logger.error(
                "[%s] phone webhook error: %s",
                self.strategy_type,
                e,
                exc_info=True,
            )
            return {"ok": True}

    async def _download_call_record(
        self,
        connector: "ChatConnector",
        adapter: "PhoneMessageAdapter",
    ) -> bytes | None:
        """Скачать запись разговора. По умолчанию — HTTP GET по call_record_url.
        Провайдеры переопределяют (напр. запрос к API по filename)."""
        url = adapter.call_record_url
        if not url:
            return None
        content, _mimetype = await self.file_download(connector, url)
        return content

    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "Contact",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
        thread_message_id: str | None = None,
        attachments: list | None = None,
    ) -> Tuple[str, str]:
        """Инициация исходящего звонка — по умолчанию не поддерживается."""
        raise NotImplementedError(
            f"Outgoing calls not supported for {self.strategy_type}"
        )
