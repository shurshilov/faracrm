# Copyright 2025 FARA CRM
# Chat module - external message model

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
    from backend.base.crm.chat.models.chat_message import ChatMessage
    from backend.project_setup import ChatConnector


class ChatExternalMessage(DotModel):
    """
    Связь между внутренним сообщением FARA CRM и внешним сообщением.

    Позволяет:
    - Отслеживать какое внутреннее сообщение соответствует какому внешнему
    - Избегать дублирования сообщений при получении вебхуков
    - Связывать отправленные сообщения с их внешними ID
    """

    __table__ = "chat_external_message"

    # (external_id, connector_id) — ключ поиска и у find_by_external_id
    # (дедуп входящих на каждом тике крона), и у find_chat_by_external_ids
    # (резолв треда письма). Индексов не было вообще → seq scan по таблице,
    # которая растёт с каждым сообщением.
    __indexes__ = [
        ("external_id", "connector_id"),
    ]

    id: int = Integer(primary_key=True)

    # Внешний идентификатор сообщения
    external_id: str = Char(
        max_length=255,
        required=True,
        description="ID сообщения во внешней системе",
    )

    # ID внешнего чата (для быстрого поиска)
    external_chat_id: str | None = Char(
        max_length=255, description="ID чата во внешней системе"
    )

    # Связь с коннектором
    connector_id: "ChatConnector" = Many2one(
        relation_table=lambda: env.models.chat_connector,
        required=True,
        ondelete="cascade",
        description="Коннектор",
    )

    # Связь с внутренним сообщением
    message_id: "ChatMessage" = Many2one(
        relation_table=lambda: env.models.chat_message,
        required=True,
        ondelete="cascade",
        description="Внутреннее сообщение FARA CRM",
    )

    # Временные метки
    create_datetime: datetime = Datetime(
        default=lambda: datetime.now(timezone.utc)
    )

    @hybridmethod
    async def find_by_external_id(
        self,
        external_id: str,
        connector_id: int,
        external_chat_id: str | None = None,
    ):
        """
        Найти связь по внешнему ID сообщения.

        Args:
            external_id: Внешний ID сообщения
            connector_id: ID коннектора
            external_chat_id: ID внешнего чата (опционально для уточнения)
        """
        filter_conditions = [
            ("external_id", "=", external_id),
            ("connector_id", "=", connector_id),
        ]

        if external_chat_id:
            filter_conditions.append(
                ("external_chat_id", "=", external_chat_id)
            )

        results = await self.search(filter=filter_conditions, limit=1)

        return results[0] if results else None

    @hybridmethod
    async def exists(self, external_id: str, connector_id: int) -> bool:
        """
        Проверить существует ли сообщение с данным внешним ID.
        Используется для избежания дублей при обработке вебхуков.
        """
        existing = await self.find_by_external_id(external_id, connector_id)
        return existing is not None

    @hybridmethod
    async def thread_outgoing_id(
        self, chat_id: int, connector_id: int
    ) -> str | None:
        """
        ИСХОДЯЩЕЕ: внешний id ПОСЛЕДНЕГО сообщения этого чата (или None).

        Для email это Message-ID последнего письма — его кладём в In-Reply-To
        нового, чтобы почтовик получателя собрал переписку в одну ветку.

        Одного id (последнего) достаточно: на маршрутизацию это не влияет
        (ответ клиента вернёт наш Message-ID сам, его ставит его почтовик), а
        для «сшивания ветки» хватает ссылки на предыдущее письмо.
        """
        session = self._get_db_session()
        rows = await session.execute(
            """
            SELECT em.external_id
            FROM chat_external_message em
            JOIN chat_message m ON m.id = em.message_id
            WHERE m.chat_id = %s AND em.connector_id = %s
            ORDER BY em.id DESC
            LIMIT 1
            """,
            (chat_id, connector_id),
        )
        return rows[0]["external_id"] if rows else None

    @hybridmethod
    async def thread_incoming_chat(
        self, external_ids: list[str], connector_id: int
    ) -> "Chat | None":
        """
        ВХОДЯЩЕЕ: в какой чат лёг тред, на который отвечает это сообщение.

        Вход — СПИСОК (не один id), и это намеренно: входящее письмо несёт в
        заголовках References целую цепочку + In-Reply-To. Ищем по совпадению с
        ЛЮБЫМ из них (пересечение множеств), потому что клиент или релей может
        срезать часть заголовков — уцелевшего одного хватит, чтобы узнать чат.
        Из совпавших берём самый свежий.

        Возвращает (chat_id, chat.active) или None. active отдаём вместе с
        chat_id (тем же запросом, JOIN chat), чтобы вызывающий не делал
        отдельный SELECT для реактивации удалённого чата. None — не ошибка:
        письмо могло прийти новым, а не ответом; вызывающий откатится на
        поиск по адресу.
        """
        if not external_ids:
            return None

        session = self._get_db_session()
        rows = await session.execute(
            """
            SELECT m.chat_id, c.active
            FROM chat_external_message em
            JOIN chat_message m ON m.id = em.message_id
            JOIN chat c ON c.id = m.chat_id
            WHERE em.external_id = ANY(%s::text[])
              AND em.connector_id = %s
            ORDER BY em.id DESC
            LIMIT 1
            """,
            (list(external_ids), connector_id),
        )
        if not rows:
            return None
        return env.models.chat(id=rows[0]["chat_id"], active=rows[0]["active"])

    @hybridmethod
    async def create_link(
        self,
        external_id: str,
        connector_id: int,
        message_id: int,
        external_chat_id: str | None = None,
    ):
        """
        Создать связь между внешним и внутренним сообщением.
        """

        link = ChatExternalMessage(
            external_id=external_id,
            external_chat_id=external_chat_id,
            connector_id=env.models.chat_connector(id=connector_id),
            message_id=env.models.chat_message(id=message_id),
        )

        link.id = await self.create(payload=link)
        return link
