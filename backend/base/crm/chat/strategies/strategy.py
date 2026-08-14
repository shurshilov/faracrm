# Copyright 2025 FARA CRM
# Chat module - base strategy pattern

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Tuple
import logging
import mimetypes

from backend.base.system.core.enviroment import env
from backend.base.crm.chat.strategies.pipeline_incoming import (
    IncomingMessagePipeline,
)

if TYPE_CHECKING:
    from datetime import datetime
    from backend.base.system.core.enviroment import Environment
    from backend.project_setup import ChatConnector
    from backend.base.crm.attachments.models.attachments import Attachment
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )
    from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter

logger = logging.getLogger(__name__)


class ChatStrategyBase(ABC):
    """
    Базовый класс стратегии для работы с внешними сервисами.

    Реализует паттерн Strategy для легкого добавления новых провайдеров
    (Telegram, WhatsApp, Avito и т.д.) без изменения основного кода.

    Каждый провайдер реализует свой класс стратегии, наследуя от этого.

    Шаблонный метод handle_webhook содержит общую логику обработки
    входящих сообщений. Конкретные стратегии переопределяют только
    create_message_adapter для парсинга специфичного формата.
    """

    # Уникальный тип стратегии (должен совпадать с connector.type)
    strategy_type: str = ""

    # Умеет ли стратегия слать вложения ВНУТРИ сообщения (одним отправлением).
    #
    # False (дефолт) — база шлёт каждое вложение отдельным вызовом
    # chat_send_message_binary. Для мессенджеров это верно: в Telegram/Avito
    # файл — самостоятельное сообщение.
    # True — база НЕ крутит цикл, а передаёт список в chat_send_message, и
    # стратегия сама укладывает файлы в одно отправление. Так делает email:
    # формат письма ровно для этого и придуман (multipart/mixed), а раньше
    # «текст + 2 файла» уходило ТРЕМЯ письмами.
    attachments_inline: bool = False

    # Умеет ли канал нести в самом сообщении пометку «это ответ на такое-то».
    #
    # True только у email: письмо несёт её заголовком In-Reply-To, и почтовик
    # получателя собирает переписку в одну ветку. У мессенджеров такого нет и
    # не нужно — там тред задаёт платформа, а приложить свой заголовок к
    # сообщению Telegram/Avito нельзя.
    #
    # НА МАРШРУТИЗАЦИЮ НЕ ВЛИЯЕТ: ответ клиента несёт In-Reply-To с нашим
    # Message-ID в любом случае — его ставит почтовик клиента, а не мы. Этот
    # флаг нужен только чтобы НАШИ письма не рассыпались у клиента в ящике.
    supports_thread: bool = False

    # Нужен ли коннектору outbox-аккаунт (chat_external_account) для отправки.
    # Для большинства провайдеров (Telegram, Avito, WhatsApp) — да: исходящие
    # идут «от» конкретного внешнего аккаунта, и send_outgoing_message без него
    # молча ничего не шлёт. Email адресуется своими полями (email_from/
    # email_username), внешний аккаунт ему не нужен — стратегия ставит False.
    requires_outbox_account: bool = True

    # В каком виде канал отдаёт бинарные данные вложения:
    #   "url"     — ссылка или идентификатор, файл надо скачать (мессенджеры);
    #   "content" — байты уже лежат в самом сообщении (почта).
    attachments_source = "url"

    # ========================================================================
    # Абстрактные методы - должны быть реализованы в каждой стратегии
    # ========================================================================

    @abstractmethod
    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """
        Получить существующий access token или сгенерировать новый.

        Должен проверить срок действия текущего токена и при необходимости
        использовать refresh_token для получения нового.

        Args:
            connector: Экземпляр коннектора

        Returns:
            Access token или None если не удалось получить
        """

    @abstractmethod
    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        Установить webhook URL для получения сообщений от провайдера.

        Args:
            connector: Экземпляр коннектора

        Returns:
            True если успешно, иначе выбрасывает исключение
        """

    @abstractmethod
    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """
        Удалить webhook.

        Args:
            connector: Экземпляр коннектора

        Returns:
            Ответ от API провайдера
        """

    @abstractmethod
    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
        thread_message_id: str | None = None,
        attachments: list | None = None,
    ):
        """
        Отправить текстовое сообщение.

        Последние два параметра база передаёт ВСЕГДА, но заполняет только тем
        стратегиям, которые это объявили (см. supports_thread и
        attachments_inline). Остальные получают None и просто их игнорируют —
        так интерфейс честно говорит, ЧТО конвейер умеет дать, а стратегия
        берёт что нужно.

        Args:
            connector: Экземпляр коннектора
            user_from: Контакт отправителя
            body: Текст сообщения
            chat_id: ID внешнего чата (если известен)
            recipients_ids: Список получателей (если нет chat_id)
            thread_message_id: внешний id предыдущего сообщения чата — чтобы пометить
                исходящее ответом на него (у email → заголовок In-Reply-To).
                Не None только при supports_thread.
            attachments: файлы В ЭТО ЖЕ сообщение. Не None только при
                attachments_inline; иначе они уже ушли отдельными вызовами
                chat_send_message_binary.

        Returns:
            Tuple[external_message_id, external_chat_id]
        """

    @abstractmethod
    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> "ChatMessageAdapter":
        """
        Создать адаптер для парсинга сырого сообщения от провайдера.

        Каждая стратегия реализует свой адаптер для преобразования
        специфичного формата сообщения в унифицированный.

        Args:
            connector: Экземпляр коннектора
            raw_message: Сырые данные сообщения

        Returns:
            Адаптер сообщения
        """

    # ========================================================================
    # Webhook обработка - шаблонный метод с общей логикой
    # ========================================================================

    async def handle_webhook(
        self,
        connector: "ChatConnector",
        payload: dict,
        env: "Environment",
        notify: bool = True,
        generate_lead: bool = True,
    ) -> dict:
        """
        Шаблонный метод обработки входящего webhook запроса.

        Содержит общую логику:
        1. Создание адаптера сообщения
        2. Проверка на пропуск
        3. Проверка дубликатов
        4. Обработка сообщения
        5. Отправка в WebSocket

        Конкретные стратегии могут переопределить для особой логики,
        но обычно достаточно реализовать create_message_adapter.

        Args:
            connector: Экземпляр коннектора
            payload: Данные от провайдера
            env: Environment с доступом к моделям
            notify: слать ли живое WS-уведомление (попап нового сообщения).
                Импорт истории звонков из CDR выключает — событие не «новое».
            generate_lead: создавать ли лид по этому сообщению. Импорт истории
                из CDR выключает — не плодим лиды по старым звонкам.

        Returns:
            Ответ для провайдера
        """
        try:
            # 1. Создаём адаптер сообщения
            adapter = self.create_message_adapter(connector, payload)

            # 2. Проверяем нужно ли пропустить
            if adapter.should_skip:
                logger.info(
                    "[%s] Skipping message %s",
                    self.strategy_type,
                    adapter.message_id,
                )
                return {"ok": True}

            # 3. Проверяем дубликат
            if await self._is_duplicate_message(env, connector, adapter):
                logger.info(
                    "[%s] Duplicate message %s",
                    self.strategy_type,
                    adapter.message_id,
                )
                return {"ok": True}

            # 4. Обрабатываем сообщение в транзакции
            async with env.apps.db.get_transaction():
                await IncomingMessagePipeline(
                    self,
                    env,
                    connector,
                    adapter,
                    notify=notify,
                    generate_lead=generate_lead,
                ).run()

            return {"ok": True}

        except NotImplementedError as e:
            logger.warning("[%s] Not implemented: %s", self.strategy_type, e)
            return {"ok": True}
        except Exception as e:
            logger.error(
                "[%s] Error processing webhook: %s",
                self.strategy_type,
                e,
                exc_info=True,
            )
            # Возвращаем OK чтобы провайдер не повторял запрос
            return {"ok": True}

    async def _is_duplicate_message(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
    ):
        """Проверить является ли сообщение дубликатом."""
        return await env.models.chat_external_message.exists(
            external_id=adapter.message_id,
            connector_id=connector.id,
        )

    async def save_attachments(
        self,
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
        message,
    ) -> list[dict]:
        """Сохранить вложения сообщения.

        Возвращает вложения в ТОМ ЖЕ формате, что и REST-эндпоинт
        /messages (messages.py: словарь id/name/mimetype/size/checksum/
        is_voice/show_preview), чтобы WS-пейлоад входящего сообщения и
        дозагрузка страницы рендерились фронтом одинаково. Нет вложений — [].
        """
        attachments: list["Attachment"] = []
        # images/files по контракту — списки, но некоторые адаптеры отдают
        # None (напр. Avito.images для не-картиночных сообщений). Страхуемся:
        # иначе распаковка [*None] падает и ТЕРЯЕТ всё сообщение.
        media = [*(adapter.images or []), *(adapter.files or [])]
        for index, item in enumerate(media, 1):
            # Часть каналов отдаёт картинки просто ссылкой.
            if not isinstance(item, dict):
                item = {"url": item}

            if self.attachments_source == "content":
                content, fetched = item["content"], None
            else:
                content, fetched = await self.file_download(connector, item)

            # Тип от канала точнее заголовка, но каналы подставляют
            # octet-stream как свой фолбэк — им заголовок не затираем.
            mimetype = item.get("mime_type")
            # Имя от канала, если есть: у письма это настоящее имя файла.
            # Свой фолбэк нумеруем, иначе безымянные вложения одного
            # сообщения получат одинаковое имя.
            # mimetype бывает None (Telegram-фото / Avito-картинки не несут
            # его в сообщении) — guess_extension(None) падает на Python 3.12.
            ext = ""
            if mimetype:
                ext = mimetypes.guess_extension(mimetype) or ""
            attachments.append(
                env.models.attachment(
                    name=item.get("name")
                    or item.get("file_name")
                    or f"{self.strategy_type}_{message.id}_{index}{ext}",
                    mimetype=mimetype,
                    size=len(content),
                    content=content,
                    res_model="chat_message",
                    res_id=message.id,
                    is_voice=item.get("is_voice", False),
                )
            )

        logger.info(
            "[%s] Attachments: %s",
            self.strategy_type,
            [a.name for a in attachments],
        )

        if not attachments:
            # Нет вложений — отдаём [], а не None: вызывающий код кладёт
            # его в WS-пейлоад как "attachments": [] (пустой, но валидный).
            return []

        await env.models.attachment.create_bulk(attachments)

        # Перечитываем из БД теми же полями, что и REST /messages. На
        # in-memory объектах незаданные поля (is_voice/show_preview)
        # читаются как None вместо дефолта БД — точного совпадения с REST
        # не дают. Чтение идёт в той же внешней транзакции (create_bulk —
        # вложенный SAVEPOINT на том же соединении), поэтому видит свои же
        # ещё не закоммиченные строки.
        rows = await env.models.attachment.search(
            filter=[
                ("res_model", "=", "chat_message"),
                ("res_id", "=", message.id),
            ],
            fields=[
                "id",
                "name",
                "mimetype",
                "size",
                "checksum",
                "is_voice",
                "show_preview",
            ],
        )
        # Единый сериализатор вложения — метод модели вложения; та же форма,
        # что и REST /messages (см. get_messages).
        return [att.serialize_for_chat() for att in rows]

    # Лидогенерация
    async def _fetch_item_info(
        self,
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
    ) -> tuple[str, str]:
        """Получить (item_title, item_url) у стратегии.

        Не все коннекторы поддерживают объявления/контекст; такие
        вернут пустые строки. Avito-стратегия переопределяет
        `get_item_info` и возвращает реальные данные.
        """
        item_title = ""
        item_url = ""
        try:
            user_id = adapter.user_id
            item_id = adapter.item_id
            chat_id = adapter.chat_id
            # user_id может быть методом — это известно для Avito-адаптера
            # if callable(user_id):
            #     user_id = user_id()
            get_item_info = getattr(self, "get_item_info", None)
            if get_item_info is not None and chat_id:
                info = (
                    await get_item_info(
                        connector, user_id, item_id, chat_id=chat_id
                    )
                    or {}
                )
                item_title = info.get("title") or ""
                item_url = info.get("url") or ""
            else:
                # Fallback на отдельный get_item_url, если стратегия даёт только его.
                if item_id and user_id:
                    item_url = (
                        await self.get_item_url(connector, user_id, item_id)
                        or ""
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] Cannot fetch item info: %s",
                self.strategy_type,
                exc,
            )
        return item_title, item_url

    # ========================================================================
    # Дополнительные методы
    # ========================================================================

    async def get_webhook_info(self, connector: "ChatConnector") -> dict:
        """
        Получить информацию о текущем webhook.

        Args:
            connector: Экземпляр коннектора

        Returns:
            Словарь с информацией о webhook
        """
        return {}

    async def delete_webhook_by_url(
        self, connector: "ChatConnector", webhook_url: str
    ) -> Any:
        """
        Удалить webhook/подписку по произвольному URL.

        Актуально для провайдеров, где подписок может быть несколько
        (MAX: список /subscriptions) и надо почистить старые. Базовая
        реализация не поддерживает — переопределяют конкретные стратегии.
        """
        raise NotImplementedError(
            f"delete_webhook_by_url not supported for {self.strategy_type}"
        )

    async def get_self_account_id(self, connector: "ChatConnector") -> dict:
        """
        Получить информацию об аккаунте от внешнего сервиса.

        Конкретные стратегии (Avito) переопределяют — возвращают данные
        текущего аккаунта (id, name, email, phone, profile_url и т.п.),
        чтобы пользователь мог скопировать `external_account_id` при
        настройке коннектора.

        Returns:
            Словарь с данными аккаунта от провайдера.
        """
        raise NotImplementedError(
            f"get_self_account_id not supported for {self.strategy_type}"
        )

    async def test_connection(self, connector: "ChatConnector") -> dict:
        """
        Проверить соединение с внешним сервисом по текущим настройкам.

        Конкретные стратегии (например Email — SMTP/IMAP логин)
        переопределяют. Возвращает словарь вида:
            {"ok": bool, "message": str, "details": {...}}

        База не умеет проверять соединение универсально, поэтому по
        умолчанию сообщает, что проверка для типа не поддерживается.
        """
        return {
            "ok": False,
            "message": (
                f"Проверка соединения не поддерживается для "
                f"типа '{self.strategy_type}'"
            ),
            "details": {},
        }

    async def sync_numbers(self, connector: "ChatConnector", env) -> dict:
        """
        Синхронизировать номера / операторские линии из внешней системы.

        Телефонные стратегии (Asterisk) переопределяют: тянут endpoints из АТС и
        создают/обновляют операторские линии (ChatExternalAccount), сопоставляя
        сотрудника по контакту (sip extension / phone). База — не поддерживает.
        Возвращает {"ok": bool, "message": str, "details": {...}}.
        """
        return {
            "ok": False,
            "message": (
                f"Синхронизация номеров не поддерживается для "
                f"типа '{self.strategy_type}'"
            ),
            "details": {},
        }

    async def import_history(
        self,
        connector: "ChatConnector",
        start_date: "datetime",
        end_date: "datetime",
        env,
        mode: str = "silent",
    ) -> dict:
        """
        Импортировать историю. Например звонки из CDR за период [start_date, end_date]
        (создать call-сообщения). Телефонные стратегии (Asterisk) переопределяют.
        База — не поддерживает. Возвращает {"ok", "message", "imported"}.

        mode — режим обработки CDR: normal (как живой звонок) / no_notify (без
        попапа) / silent (без попапа и без лида, по умолчанию).
        """
        return {
            "ok": False,
            "imported": 0,
            "message": (
                f"Импорт истории звонков не поддерживается для "
                f"типа '{self.strategy_type}'"
            ),
        }

    async def set_listener(
        self, connector: "ChatConnector", enabled: bool, env
    ) -> dict:
        """
        Включить/выключить постоянный in-process слушатель событий провайдера
        (напр. Asterisk ARI в local-режиме). База не поддерживает.
        Возвращает {"ok": bool, "enabled": bool, "message": str}.
        """
        return {
            "ok": False,
            "enabled": False,
            "message": (
                f"Слушатель событий не поддерживается для "
                f"типа '{self.strategy_type}'"
            ),
        }

    async def chat_send_message_binary(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        chat_id: str,
        attachment: Any,
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить файл или изображение.

        Args:
            connector: Экземпляр коннектора
            user_from: Контакт отправителя
            chat_id: ID внешнего чата
            attachment: Вложение для отправки
            recipients_ids: Список получателей

        Returns:
            Tuple[external_message_id, external_chat_id]
        """
        raise NotImplementedError(
            f"Binary messages not supported for {self.strategy_type}"
        )

    async def file_download(
        self, connector: "ChatConnector", file: dict | str
    ) -> tuple[bytes, str]:
        """
        Скачать файл по ссылке.

        Args:
            connector: Экземпляр коннектора
            file: элемент adapter.images/files — словарь канала или сам URL.
                Каналы, адресующие файл иначе (Telegram — file_id), метод
                переопределяют и читают свои ключи сами.

        Returns:
            Содержимое файла в байтах и его MIME-тип
        """
        import httpx

        file_url = file["url"] if isinstance(file, dict) else file

        # follow_redirects: у httpx это не поведение по умолчанию, а CDN
        # мессенджеров отвечают 302. raise_for_status: иначе страница ошибки
        # сохранится как вложение с правильным именем.
        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True
        ) as client:
            response = await client.get(file_url)
            response.raise_for_status()
            # Получаем MIME-тип и очищаем его от возможных параметров вроде charset=utf-8
            content_type = response.headers.get("content-type", "")
            mime_type = (
                content_type.split(";")[0].strip()
                if content_type
                else "unknown"
            )

            # Теперь у вас есть доступ и к mime_type, и к response.content
            return response.content, mime_type

    async def get_item_url(
        self, connector: "ChatConnector", user_id: str, item_id: str
    ) -> str | None:
        """
        Получить URL элемента (например, объявления в Avito).

        Args:
            connector: Экземпляр коннектора
            user_id: ID пользователя
            item_id: ID элемента

        Returns:
            URL элемента или None
        """
        return None

    async def send_outgoing_message(
        self,
        env: "Environment",
        chat_id: int,
        connector_id: "ChatConnector",
        user_id: int,
        body: str,
        message_id: int,
        attachments: list["Attachment"] | None = None,
        recipients_ids: list[dict] | None = None,
    ):
        """
        Отправить сообщение во внешний коннектор (Telegram, WhatsApp и т.д.)

        Args:
            env: Environment
            chat_id: ID внутреннего чата
            connector_id: коннектор
            user_id: ID пользователя-отправителя
            body: Текст сообщения
            message_id: ID внутреннего сообщения
            attachments: Список вложений [{id, name, mimetype, size, content}]
            recipients_ids: Список контактов получателей [{"id": ..., "contact_value": ...}]

        Returns:
            True если успешно отправлено
        """
        try:
            # Находим external_chat для этого чата и коннектора
            external_chat = await env.models.chat_external_chat.search(
                filter=[
                    ("chat_id", "=", chat_id),
                    ("connector_id", "=", connector_id.id),
                ],
                fields=["id", "external_id"],
                limit=1,
            )

            external_chat_id = None
            # Флаг write-first: связи ещё нет, адресуем по контакту получателя.
            # Ниже, ПОСЛЕ отправки, персистим external_chat (иначе входящий
            # ответ не найдёт связь и создаст второй внутренний чат).
            is_write_first = False
            write_first_address = None

            if external_chat:
                # Есть существующий external_chat - используем его
                external_chat_id = external_chat[0].external_id
            elif recipients_ids:
                # Первое сообщение - используем контакты получателей
                # Пока поддерживаем отправку только одному получателю
                if len(recipients_ids) > 1:
                    logger.warning(
                        "Multiple recipients not fully supported yet, using first one"
                    )

                recipient = recipients_ids[0]
                external_chat_id = recipient["contact_value"]
                is_write_first = True
                write_first_address = external_chat_id
            else:
                logger.warning(
                    "No external_chat found for chat=%s, connector=%s and no recipients provided",
                    chat_id,
                    connector_id.id,
                )
                return False

            # Находим контакт оператора по contact_type_id коннектора
            # operator_ct_id = connector_id.contact_type_id
            # if operator_ct_id is None:
            #     raise ValueError("Contact type must be set")

            # operator_contact = await env.models.contact.search(
            #     filter=[
            #         ("contact_type_id", "=", operator_ct_id),
            #         ("user_id", "=", user_id),
            #         ("active", "=", True),
            #     ],
            #     fields_nested={"external_account_ids": ["id"]},
            #     limit=1,
            # )

            # if not operator_contact:
            #     logger.warning(
            #         "No operator contact found for connector %s, user %s",
            #         connector_id.id,
            #         user_id,
            #     )
            #     return False

            # Отправляем, если есть outbox-аккаунт ИЛИ стратегия его не требует
            # (email адресуется своими полями). Раньше здесь стоял голый
            # `if connector_id.outbox_account_id:` — у email он всегда None
            # (external_account_id не заполняется), поэтому весь блок отправки
            # пропускался, функция возвращала None, а сообщение оставалось
            # внутренним. Именно поэтому письмо «не уходило».
            outbox = connector_id.outbox_account_id
            if outbox or not self.requires_outbox_account:
                external_msg_id = None

                # Вложения внутри сообщения (email) или отдельными (мессенджеры)
                inline = bool(attachments) and self.attachments_inline

                # Пометка «это ответ на такое-то» для исходящего — только тем,
                # кто умеет её нести. Берём ПОСЛЕДНЕЕ сообщение чата: этого
                # хватает, чтобы почтовик получателя собрал переписку в ветку.
                # На маршрутизацию не влияет, см. supports_thread.
                thread_message_id = None
                if self.supports_thread:
                    thread_message_id = await env.models.chat_external_message.thread_outgoing_id(
                        chat_id=chat_id,
                        connector_id=connector_id.id,
                    )

                # Отправляем вложения ОТДЕЛЬНЫМИ сообщениями — только если
                # стратегия не умеет иначе. У email умеет: там они уедут внутри
                # письма ниже, одним отправлением.
                if attachments and not inline:
                    for att in attachments:
                        try:
                            # Получаем содержимое вложения из БД
                            # attachment = await env.models.attachment.get(att["id"])
                            # if not attachment:
                            #     continue
                            file_msg_id = await self.chat_send_message_binary(
                                connector_id,
                                outbox,
                                external_chat_id,
                                att,
                            )

                            if file_msg_id and not external_msg_id:
                                external_msg_id = file_msg_id

                        except Exception as e:
                            # att — объект Attachment (см. messages.py, там
                            # собираются payload'ы модели), а не dict. Раньше
                            # здесь стояло att.get("id") — обработчик ошибок сам
                            # падал на первом же сбое отправки вложения.
                            logger.error(
                                "Failed to send attachment %s: %s",
                                getattr(att, "id", None),
                                e,
                            )

                # Если нет вложений или есть текст без caption — отправляем текст.
                # При inline зовём ДАЖЕ С ПУСТЫМ текстом: иначе письмо с одними
                # файлами и без подписи не ушло бы вовсе — цикл выше пропущен, а
                # отправляет именно этот вызов.
                # Второй элемент — канонический ключ переписки, который вернула
                # стратегия (для write-first это нормализованный адрес/номер;
                # когда стратегия начнёт возвращать реальный chat_id из ответа —
                # это будет он).
                conversation_key = None
                if body.strip() or inline:
                    text_msg_id, conversation_key = (
                        await self.chat_send_message(
                            connector=connector_id,
                            user_from=outbox,
                            body=body,
                            chat_id=external_chat_id,
                            thread_message_id=thread_message_id,
                            attachments=attachments if inline else None,
                        )
                    )
                    if text_msg_id:
                        external_msg_id = text_msg_id

                # Сохраняем связь с внешним сообщением
                if external_msg_id:
                    await env.models.chat_external_message.create_link(
                        external_id=str(external_msg_id),
                        connector_id=connector_id.id,
                        message_id=message_id,
                        external_chat_id=external_chat_id,
                    )

                # Персистим связь чата при отправке-первым: без неё входящий
                # ответ не найдёт external_chat и создаст ВТОРОЙ внутренний чат.
                # external_id — ключ треда (пока = нормализованный адрес; когда
                # стратегия отдаст реальный chat_id — перезапишется на него).
                # external_address — сам адрес (номер), по нему входящий ответ
                # найдётся даже после перезаписи external_id (см.
                # ChatExternalChat.find_by_id_or_address). Идемпотентно: если
                # связь уже успел создать входящий — не дублируем.
                if is_write_first:
                    thread_key = str(conversation_key or write_first_address)
                    address_key = str(conversation_key or write_first_address)
                    # Идемпотентность — ПО АДРЕСУ, а не по chat_id.
                    already = await env.models.chat_external_chat.find_by_id_or_address(
                        key=address_key,
                        connector_id=connector_id.id,
                    )
                    if not already:
                        await env.models.chat_external_chat.create_link(
                            external_id=thread_key,
                            connector_id=connector_id.id,
                            chat_id=chat_id,
                            external_address=address_key,
                        )
                        logger.info(
                            "write-first external_chat linked: chat=%s "
                            "connector=%s address=%s",
                            chat_id,
                            connector_id.id,
                            address_key,
                        )
                    else:
                        # Связь на этот адрес уже есть и ведёт в другой чат —
                        # НЕ дублируем: диалог принадлежит тому чату, и входящий
                        # ответ уйдёт туда. Иначе получили бы два чата на адрес.
                        linked_chat = already.chat_id
                        if linked_chat != chat_id:
                            logger.warning(
                                "write-first: адрес %s уже привязан к чату %s "
                                "(коннектор %s), отправка идёт из чата %s — "
                                "ответ придёт в %s, связь не дублируем.",
                                address_key,
                                linked_chat,
                                connector_id.id,
                                chat_id,
                                linked_chat,
                            )

                logger.info(
                    "Sent message to %s: internal=%s, external=%s",
                    connector_id.type,
                    message_id,
                    external_msg_id,
                )
                return True

        except Exception as e:
            logger.error(
                "Failed to send to external connector: %s", e, exc_info=True
            )
            return False

    async def resolve_partner_id_and_name(
        self,
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
    ) -> tuple[str | None, str | None]:
        """Хук: вернуть (external_id, name) клиента-контрагента.

        По умолчанию контрагент = автор сообщения. Это верно для коннекторов,
        куда webhook приходит только на входящие сообщения от клиента
        (Telegram, WhatsApp, email и т.п.).

        Avito переопределяет: туда webhook приходит и на наши собственные
        исходящие, поэтому клиента (id и имя) нужно определять по участникам
        чата, а не по author_id.

        external_id=None означает «не удалось определить клиента» — обработка
        сообщения будет пропущена, чтобы не
        создавать партнёра/лид на наш собственный аккаунт.
        """
        return adapter.author_id, adapter.author_name
