# Copyright 2025 FARA CRM
# Chat module - external chat model

from datetime import datetime, timezone
from typing import TYPE_CHECKING


from backend.base.system.dotorm.dotorm.decorators import hybridmethod
from backend.base.system.dotorm.dotorm.fields import (
    Integer,
    Char,
    Datetime,
    Many2one,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env

if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat import Chat
    from backend.project_setup import ChatConnector


class ChatExternalChat(DotModel):
    """
    Связь между внутренним чатом FARA CRM и внешним чатом в стороннем сервисе.

    Позволяет отслеживать какой внутренний чат соответствует какому внешнему.
    Один внутренний чат может иметь несколько внешних связей
    (например, клиент пишет и в Telegram, и в WhatsApp).
    """

    __table__ = "chat_external_chat"

    __indexes__ = [
        ("chat_id", "connector_id", "id"),
    ]
    id: int = Integer(primary_key=True)

    # Внешний идентификатор чата в стороннем сервисе.
    # Каналы с реальным thread-id (Telegram/Avito/MAX после reconcile) хранят
    # тут id переписки. При отправке-первым по номеру (write-first) сюда
    # кладётся бутстрап-ключ (нормализованный адрес), который позже
    # перезаписывается на реальный chat_id, когда стратегия его вернёт.
    external_id: str = Char(
        max_length=255, required=True, description="ID чата во внешней системе"
    )

    # Адрес получателя, которым инициировали переписку (номер телефона для
    # write-first каналов: max_business, whatsapp). Стабильный per-(чат,
    # коннектор) ключ. Нужен, чтобы входящий ответ нашёл эту связь по номеру,
    # даже если external_id уже перезаписан на платформенный chat_id.
    # Для каналов без адресации по номеру (Telegram/Avito) остаётся пустым.
    external_address: str | None = Char(
        max_length=255,
        description="Адрес инициации (номер) для write-first каналов",
        index=True,
    )

    # Связь с коннектором
    connector_id: "ChatConnector" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        required=True,
        ondelete="cascade",
        description="Коннектор",
    )

    # Связь с внутренним чатом
    chat_id: "Chat" = Many2one(
        relation_table=lambda: env.models.chat,
        required=True,
        ondelete="cascade",
        description="Внутренний чат FARA CRM",
    )

    # Кеш для Avito и подобных площадок
    item_title: str | None = Char(
        max_length=500,
        description="Заголовок объявления/контекста (для Avito и т.п.)",
    )
    item_url: str | None = Char(
        max_length=500,
        description="URL объявления/контекста (для Avito и т.п.)",
    )

    # Временные метки
    create_datetime: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc)
    )

    @hybridmethod
    async def find_by_external_id(self, external_id: str, connector_id: int):
        """
        Найти связь по внешнему ID чата и коннектору.
        """
        results = await self.search(
            filter=[
                ("external_id", "=", external_id),
                ("connector_id", "=", connector_id),
            ],
            fields=["chat_id", "item_title", "item_url"],
            limit=1,
        )

        return results[0] if results else None

    @hybridmethod
    async def find_by_id_or_address(self, key: str, connector_id: int):
        """
        Найти связь по ключу входящего, совпадающему С external_id ЛИБО
        external_address. Нужно для write-first каналов: мы могли создать связь
        по номеру (external_address), а платформа прислала ответ по своему
        chat_id (external_id) — или наоборот.

        Совпадение по external_id ЛИБО external_address, И тот же коннектор:
        (external_id = key OR external_address = key) AND connector_id = cid.
        """
        results = await self.search(
            filter=[
                [
                    ("external_id", "=", key),
                    "or",
                    ("external_address", "=", key),
                ],
                "and",
                ("connector_id", "=", connector_id),
            ],
            fields=["chat_id", "item_title", "item_url", "external_id"],
            limit=1,
        )

        return results[0] if results else None

    @hybridmethod
    async def create_link(
        self,
        external_id: str,
        connector_id: int,
        chat_id: int,
        item_title: str | None = None,
        item_url: str | None = None,
        external_address: str | None = None,
    ):
        """
        Создать связь между внешним и внутренним чатом.

        external_address — адрес инициации (номер) для write-first каналов;
        для остальных не передаётся и остаётся пустым.
        """
        link = ChatExternalChat(
            external_id=external_id,
            connector_id=env.models.chat_connector(id=connector_id),
            chat_id=env.models.chat(id=chat_id),
            item_title=item_title,
            item_url=item_url,
            external_address=external_address,
        )

        link.id = await self.create(payload=link)
        return link
