# Copyright 2025 FARA CRM
# Chat module - base message adapter

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_connector import ChatConnector


class ChatMessageAdapter:
    """
    Базовый адаптер для парсинга сообщений от разных провайдеров.

    Преобразует специфичный формат сообщения провайдера в унифицированный
    формат FARA CRM.

    Каждая стратегия реализует свой класс-наследник с парсингом
    специфичного формата.

    Пример реализации для Telegram:

        class TelegramMessageAdapter(ChatMessageAdapter):
            @property
            def message_id(self) -> str:
                return str(self.raw.get("message", {}).get("message_id", ""))

            @property
            def chat_id(self) -> str:
                return str(self.raw.get("message", {}).get("chat", {}).get("id", ""))
            ...
    """

    def __init__(self, connector: "ChatConnector", raw: dict):
        """
        Args:
            connector: Экземпляр коннектора
            raw: Сырые данные сообщения от провайдера
        """
        self.connector = connector
        self.raw = raw

    @property
    def message_id(self) -> str:
        """ID сообщения во внешней системе."""
        raise NotImplementedError

    @property
    def chat_id(self) -> str:
        """ID чата во внешней системе."""
        raise NotImplementedError

    @property
    def author_id(self) -> str:
        """ID автора сообщения."""
        raise NotImplementedError

    @property
    def text(self) -> str | None:
        """Текст сообщения."""
        raise NotImplementedError

    @property
    def images(self) -> list[str]:
        """Список URL изображений или объектов с file_id."""
        return []

    @property
    def files(self) -> list[dict]:
        """
        Список файлов.

        Каждый файл - словарь с ключами:
        - url или file_id: идентификатор/путь к файлу
        - name: имя файла
        - mime_type: MIME тип
        """
        return []

    @property
    def created_at(self) -> int:
        """Unix timestamp создания сообщения."""
        raise NotImplementedError

    @property
    def author_name(self) -> str | None:
        """Имя автора (опционально)."""
        return None

    @property
    def should_skip(self) -> bool:
        """
        Нужно ли пропустить обработку сообщения.

        True для служебных сообщений, сообщений от ботов и т.д.
        """
        return False

    @property
    def is_from_external(self) -> bool:
        """
        Сообщение от внешнего пользователя (не оператора).

        Для большинства провайдеров всегда True,
        т.к. webhook'и приходят только от внешних пользователей.
        """
        return True
