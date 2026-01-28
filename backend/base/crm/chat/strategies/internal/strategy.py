# Copyright 2025 FARA CRM
# Chat module - internal strategy (for FARA CRM internal messaging)

from typing import TYPE_CHECKING, Tuple, Any
import logging

from backend.base.crm.chat.strategies.strategy import ChatStrategyBase
from backend.base.crm.chat.strategies.internal.adapter import InternalMessageAdapter

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )

logger = logging.getLogger(__name__)


class InternalStrategy(ChatStrategyBase):
    """
    Стратегия для внутреннего чата FARA CRM.

    Используется для обмена сообщениями между пользователями системы
    без интеграции с внешними сервисами.

    Основная особенность - сообщения доставляются через WebSocket
    напрямую между клиентами.
    """

    strategy_type = "internal"

    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """
        Для внутреннего чата токен не требуется.
        Авторизация происходит через стандартную систему FARA CRM.
        """
        return "internal"

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        Для внутреннего чата webhook не требуется.
        Сообщения передаются через WebSocket.
        """
        return True

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """Для внутреннего чата webhook не используется."""
        return None

    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить сообщение во внутреннем чате.

        Для внутреннего чата эта функция вызывается только при необходимости
        создать запись во внешних таблицах (например, для аудита).

        Реальная отправка происходит через:
        1. Создание записи ChatMessage
        2. Отправка через WebSocket всем подключенным участникам чата

        Returns:
            Tuple[message_id как строка, chat_id как строка]
        """
        import uuid

        # Генерируем уникальный ID для внутреннего сообщения
        internal_message_id = str(uuid.uuid4())
        internal_chat_id = chat_id or str(uuid.uuid4())

        logger.info(
            f"Internal message sent: {internal_message_id} to chat {internal_chat_id}"
        )

        return internal_message_id, internal_chat_id

    async def chat_send_message_binary(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        chat_id: str,
        attachment: Any,
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить файл во внутреннем чате.
        Файлы сохраняются через стандартную систему Attachments.
        """
        import uuid

        internal_message_id = str(uuid.uuid4())

        logger.info(
            f"Internal binary message sent: {internal_message_id} to chat {chat_id}"
        )

        return internal_message_id, chat_id

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> InternalMessageAdapter:
        """Создать адаптер для внутреннего сообщения."""
        return InternalMessageAdapter(connector, raw_message)
