# Copyright 2025 FARA CRM
# Chat module - Avito message adapter

from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter


class AvitoMessageAdapter(ChatMessageAdapter):
    """
    Адаптер для парсинга сообщений от Avito Messenger API.

    Формат входящего webhook:
    {
        "payload": {
            "value": {
                "id": "message_id",
                "chat_id": "chat_id",
                "user_id": 12345,
                "author_id": 67890,
                "type": "text",
                "chat_type": "u2i",
                "item_id": "item_123",
                "created": 1750789487,
                "content": {
                    "text": "Привет"
                }
            }
        }
    }

    Типы сообщений:
    "text" | "image" | "system" | "item" | "call" | "link" |
    "location" | "deleted" | "appCall" | "file" | "video" | "voice"
    """

    # URL для формирования ссылки на чат
    CHAT_URL = "https://www.avito.ru/profile/messenger/channel/"

    @property
    def _payload(self) -> dict:
        """Получить объект payload.value из сообщения."""
        return self.raw.get("payload", {}).get("value", {})

    @property
    def _content(self) -> dict:
        """Получить содержимое сообщения."""
        return self._payload.get("content", {})

    @property
    def message_id(self) -> str:
        """ID сообщения в Avito."""
        return str(self._payload.get("id", ""))

    @property
    def chat_id(self) -> str:
        """ID чата в Avito."""
        return str(self._payload.get("chat_id", ""))

    @property
    def author_id(self) -> str:
        """ID отправителя сообщения."""
        return str(self._payload.get("author_id", ""))

    @property
    def user_id(self) -> str:
        """
        ID пользователя-получателя (владелец webhook).
        Это аккаунт на который зарегистрирован webhook.
        """
        return str(self._payload.get("user_id", ""))

    @property
    def text(self) -> str | None:
        """Текст сообщения."""
        return self._content.get("text")

    @property
    def message_type(self) -> str:
        """
        Тип сообщения Avito.

        Enum: "text" "image" "system" "item" "call" "link"
        "location" "deleted" "appCall" "file" "video" "voice"
        """
        return self._payload.get("type", "")

    @property
    def chat_type(self) -> str:
        """
        Тип чата.

        u2i - чат по объявлению
        u2u - чат по профилю пользователя
        """
        return self._payload.get("chat_type", "")

    @property
    def item_id(self) -> str | None:
        """ID объявления (только для чатов типа u2i)."""
        return self._payload.get("item_id")

    @property
    def created_at(self) -> int:
        """Unix timestamp создания сообщения."""
        return self._payload.get("created", 0)

    @property
    def author_name(self) -> str | None:
        """
        Имя автора.

        В Avito имя получается отдельным API запросом,
        здесь возвращаем None.
        """
        return None

    @property
    def images(self) -> list[str]:
        """
        Список URL изображений.

        Avito присылает несколько размеров, выбираем 1280x960.
        """
        image_data = self._content.get("image", {})
        if not image_data:
            return []

        sizes = image_data.get("sizes", {})
        # Предпочитаем размер 1280x960, иначе берём любой доступный
        url = (
            sizes.get("1280x960")
            or sizes.get("640x480")
            or next(iter(sizes.values()), None)
        )

        return [url] if url else []

    @property
    def files(self) -> list[dict]:
        """
        Список файлов.

        Avito поддерживает типы: file, video, voice.
        """
        file_type = self.message_type
        if file_type not in ("file", "video", "voice"):
            return []

        # Для этих типов Avito возвращает empty object в content
        # Файлы нужно скачивать отдельно
        return []

    @property
    def should_skip(self) -> bool:
        """
        Определить нужно ли пропустить обработку сообщения.

        Пропускаем:
        - Системные сообщения
        - Удалённые сообщения
        - Сообщения типов appCall (не поддерживаются)
        """
        skip_types = {"system", "deleted", "appCall"}
        return self.message_type in skip_types

    @property
    def is_from_external(self) -> bool:
        """
        Сообщение от внешнего пользователя (клиента).

        В Avito webhook приходит когда клиент пишет продавцу,
        поэтому всегда True.
        """
        return True

    def get_chat_url(self) -> str:
        """Получить URL для открытия чата в веб-интерфейсе Avito."""
        return f"{self.CHAT_URL}{self.chat_id}"
