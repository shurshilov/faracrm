# Copyright 2025 FARA CRM
# Chat module - base message adapter

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.project_setup import ChatConnector


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
    def user_id(self):
        """
        ID пользователя-получателя (владелец webhook).
        Это аккаунт на который зарегистрирован webhook.
        """
        # external_account_id настроен на коннекторе — это надёжнее, чем
        # тащить значение из payload.
        return self.connector.external_account_id
        # return str(self._payload.get("user_id", ""))

    @property
    def message_id(self) -> str:
        """ID сообщения во внешней системе."""
        raise NotImplementedError()

    @property
    def chat_id(self) -> str:
        """ID чата во внешней системе."""
        raise NotImplementedError()

    @property
    def item_id(self) -> str | None:
        """ID обьявлени или связаннйо сущности во внешней системе."""
        return None

    @property
    def thread_message_ids(self) -> list[str]:
        """
        ID сообщений, по которым видно, к какой переписке относится это.

        Простыми словами: входящее может само сказать «я ответ вон на те
        сообщения». Тогда мы находим их у себя и кладём его в тот же чат.

        Есть только у email: письмо несёт эти id в заголовках. У остальных
        каналов такого нет и не нужно — там платформа сама даёт id диалога, и
        он приезжает в chat_id. Приложить что-то своё к сообщению Telegram или
        Avito всё равно нельзя.

        Поэтому дефолт — пусто, и переопределять это никто не обязан: ветка
        резолва по переписке просто не сработает.
        """
        return []

    @property
    def author_id(self) -> str:
        """ID автора сообщения."""
        raise NotImplementedError()

    @property
    def text(self) -> str | None:
        """Текст сообщения."""
        raise NotImplementedError()

    @property
    def serialized_body(self) -> str:
        """
        Тело сообщения, сериализованное для хранения в chat_message.body.

        По умолчанию — обычный текст. Провайдеры со своим форматом тела
        переопределяют: например Email сериализует {subject, html} в JSON
        (обратная операция — parse_email_body в email-стратегии). Так формат
        живёт целиком в адаптере провайдера, а вызывающий код (обработка
        входящих) единообразно берёт adapter.serialized_body без ветвлений.
        """
        return self.text or ""

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
        raise NotImplementedError()

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
