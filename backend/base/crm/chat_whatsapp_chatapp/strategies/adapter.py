# Copyright 2025 FARA CRM
# Chat module - WhatsApp ChatApp message adapter

from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter


class WhatsAppChatAppMessageAdapter(ChatMessageAdapter):
    """
    Адаптер для парсинга сообщений от WhatsApp через ChatApp API.

    Формат входящего сообщения (написали нам):
    {
        'data': [{
            'id': '3EB0AFFCCBD74DEF3A9AC7',
            'internalId': '3EB0AFFCCBD74DEF3A9AC7',
            'fromApi': False,
            'fromMe': False,
            'side': 'in',
            'time': 1752391936,
            'type': 'text',
            'message': {
                'text': 'Тест',
                'caption': '',
                'file': None
            },
            'fromUser': {
                'id': '79851111111@c.us',
                'name': 'shurshilov a a',
                'phone': '79851111111'
            },
            'chat': {
                'id': '79851111111@c.us',
                'type': 'private',
                'phone': '79851111111',
                'name': 'shurshilov a a'
            }
        }],
        'meta': {
            'type': 'message',
            'licenseId': 11111,
            'messengerType': 'grWhatsApp'
        }
    }

    Формат исходящего (написали мы):
    - fromMe: True
    - side: 'out'
    """

    @property
    def _data(self) -> dict:
        """Получить первый элемент из data."""
        data_list = self.raw.get("data", [])
        return data_list[0] if data_list else {}

    @property
    def _message(self) -> dict:
        """Получить объект message."""
        return self._data.get("message", {})

    @property
    def _from_user(self) -> dict:
        """Получить информацию об отправителе."""
        return self._data.get("fromUser", {})

    @property
    def _chat(self) -> dict:
        """Получить информацию о чате."""
        return self._data.get("chat", {})

    @property
    def _meta(self) -> dict:
        """Получить метаданные."""
        return self.raw.get("meta", {})

    @property
    def message_id(self) -> str:
        """ID сообщения в WhatsApp."""
        return str(self._data.get("id", ""))

    @property
    def chat_id(self) -> str:
        """ID чата в WhatsApp (формат: phone@c.us)."""
        return str(self._chat.get("id", ""))

    @property
    def author_id(self) -> str:
        """
        ID отправителя.

        В WhatsApp используется номер телефона как ID.
        """
        return str(self._from_user.get("phone", ""))

    @property
    def text(self) -> str | None:
        """
        Текст сообщения.

        Если текст отправлен с картинкой, то текст в caption.
        """
        return self._message.get("text") or self._message.get("caption")

    @property
    def message_type(self) -> str:
        """
        Тип сообщения.

        Типы: text, image, video, document, audio, voice, sticker, location
        """
        return self._data.get("type", "text")

    @property
    def created_at(self) -> int:
        """Unix timestamp создания сообщения."""
        return self._data.get("time", 0)

    @property
    def author_name(self) -> str | None:
        """Имя отправителя."""
        return self._from_user.get("name") or self._chat.get("name")

    @property
    def partner_name(self) -> str | None:
        """Имя клиента (из данных чата)."""
        return self._chat.get("name")

    @property
    def images(self) -> list[dict]:
        """
        Список файлов-изображений.

        ChatApp возвращает файлы в message.file с публичной ссылкой.
        """
        file_data = self._message.get("file")
        if not file_data:
            return []

        # Проверяем что это изображение
        mimetype = file_data.get("mimeType", "")
        if not mimetype.startswith("image/"):
            return []

        return [file_data]

    @property
    def files(self) -> list[dict]:
        """
        Список файлов (не изображений).

        Каждый файл содержит:
        - link: публичная ссылка для скачивания
        - name: имя файла
        - mimeType: MIME тип
        - size: размер в байтах
        """
        file_data = self._message.get("file")
        if not file_data:
            return []

        # Исключаем изображения (они обрабатываются в images)
        mimetype = file_data.get("mimeType", "")
        if mimetype.startswith("image/"):
            return []

        return [
            {
                "url": file_data.get("link", ""),
                "name": file_data.get("name", "file"),
                "mime_type": mimetype,
                "size": file_data.get("size", 0),
            }
        ]

    @property
    def is_from_me(self) -> bool:
        """Сообщение отправлено нами (оператором)."""
        return self._data.get("fromMe", False)

    @property
    def side(self) -> str:
        """
        Направление сообщения.

        'in' - входящее (от клиента)
        'out' - исходящее (от нас)
        """
        return self._data.get("side", "in")

    @property
    def should_skip(self) -> bool:
        """
        Определить нужно ли пропустить обработку.

        Пропускаем:
        - Исходящие сообщения (от нас)
        - Сообщения отправленные через API (fromApi=True и fromMe=True)
        """
        # Пропускаем исходящие сообщения
        if self.is_from_me:
            return True

        # Пропускаем если side='out'
        if self.side == "out":
            return True

        return False

    @property
    def is_from_external(self) -> bool:
        """
        Сообщение от внешнего пользователя (клиента).

        True если side='in' и fromMe=False.
        """
        return self.side == "in" and not self.is_from_me

    @property
    def license_id(self) -> int | None:
        """ID лицензии ChatApp."""
        return self._meta.get("licenseId")

    @property
    def messenger_type(self) -> str:
        """Тип мессенджера (grWhatsApp)."""
        return self._meta.get("messengerType", "grWhatsApp")

    @property
    def chat_type(self) -> str:
        """
        Тип чата.

        'private' - личный чат
        'group' - групповой чат
        """
        return self._chat.get("type", "private")

    @property
    def phone(self) -> str | None:
        """Номер телефона клиента."""
        return self._chat.get("phone") or self._from_user.get("phone")
