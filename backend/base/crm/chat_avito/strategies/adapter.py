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
        """Шорткат получить объект payload.value из сообщения."""
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

    def user_id(self):
        """
        ID пользователя-получателя (владелец webhook).
        Это аккаунт на который зарегистрирован webhook.
        """
        # external_account_id настроен на коннекторе — это надёжнее, чем
        # тащить значение из payload.
        return self.connector.external_account_id
        # return str(self._payload.get("user_id", ""))

    # @property
    # def type(self) -> str:
    #     """Тип сообщения
    #     Enum: "text" "image" "system" "item" "call" "link"
    #     "location" "deleted" "appCall" "file" "video" "voice"
    #     """
    #     return self._payload.get("type")

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

    # @property
    # def created(self) -> datetime | None:
    #     """Unix-timestamp времени отправки сообщения.

    #     BUGFIX: ``datetime.fromtimestamp(None)`` валится с TypeError —
    #     раньше из-за этого падал каждый webhook без таймстампа.
    #     """
    #     timestamp = self._payload.get("created")
    #     if not timestamp:
    #         return None
    #     try:
    #         return datetime.fromtimestamp(int(timestamp))
    #     except (TypeError, ValueError, OSError) as exc:
    #         _logger.warning(
    #             "Avito message: bad created timestamp %r: %s", timestamp, exc
    #         )
    #         return None

    @property
    def created_at(self) -> int:
        """Unix timestamp создания сообщения."""
        return self._payload.get("created", 0)

    # @property
    # def id(self) -> str:
    #     """Уникальный идентификатор сообщения"""
    #     return self._payload.get("id")

    @property
    def author_name(self) -> str | None:
        """
        Имя автора.

        В Avito имя получается отдельным API запросом,
        здесь возвращаем None.
        """
        return None

    @property
    def text(self):
        """Для сообщений типов "appCall" "file" "video"
        возвращается empty object (данные типы не поддерживаются).
        """
        content = self._content
        if "text" in content:
            return content.get("text")
        # Для сообщений типа item Avito не присылает text, но в content
        # есть item.title — отдадим его как текст, чтобы лента не была
        # пустой.
        item = content.get("item") or {}
        if item.get("title"):
            return item.get("title")
        return None

    @property
    def images(self):
        """
        Список URL изображений.

        Avito присылает несколько размеров, выбираем 1280x960.

        Для сообщений типов "appCall" "file" "video"
        возвращается empty object (данные типы не поддерживаются).
        """
        content = self._content
        if "image" not in content:
            return None
        image = content.get("image") or {}
        sizes = image.get("sizes") or {}
        # пытаемся отдать самый большой доступный размер
        for size in ("1280x960", "640x480", "140x105", "32x32"):
            url = sizes.get(size)
            if url:
                # в авито в сообщении может быть только одно фото,
                # но в других интеграциях может быть много →
                # оборачиваем в список для совместимости с базой
                return [url]
        return None

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
        """Пропускаем сообщения, которые не имеют смысла обрабатывать.

        Раньше базовый ChatMessageAdapter.__init__ просто кидал
        ValidationError если text и image оба пустые — webhook падал 500
        и Avito ретраил его до бесконечности.
        Теперь скип-и для типов вроде appCall/file/video/system/deleted/voice/call/location.
        """
        skip_types = {
            "appCall",
            "file",
            "video",
            "voice",
            "call",
            "system",
            "deleted",
            "location",
            "link",
        }
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
