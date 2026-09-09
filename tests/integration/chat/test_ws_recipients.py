# Copyright 2025 FARA CRM
"""
Адресаты WS-событий чата — ChatMember.active_user_ids.

Список считает сервер из chat_member (клиентских подписок больше нет), поэтому
важны два свойства: только активные пользователи-участники, и видимость
участника, добавленного в ещё не закоммиченной транзакции — событие о его
добавлении публикуется в той же транзакции.

Run: pytest tests/integration/chat/test_ws_recipients.py -v -m integration
"""

import pytest

from backend.base.crm.chat.models.chat import Chat
from backend.base.crm.chat.models.chat_member import ChatMember
from backend.base.system.dotorm.dotorm.databases.postgres.transaction import (
    ContainerTransaction,
)

pytestmark = [pytest.mark.integration]

# Сидятся фикстурами тестовой БД (см. conftest).
ADMIN_ID = 1
SYSTEM_ID = 2


class TestActiveUserIds:
    async def test_returns_only_active_user_members(
        self, authenticated_client
    ):
        _, user_id, _ = authenticated_client
        chat_id = await Chat.create(Chat(name="Recipients"))
        await ChatMember.create(
            ChatMember(chat_id=chat_id, user_id=user_id, is_active=True)
        )
        await ChatMember.create(
            ChatMember(chat_id=chat_id, user_id=ADMIN_ID, is_active=True)
        )
        # Вышедший из чата — не адресат.
        await ChatMember.create(
            ChatMember(chat_id=chat_id, user_id=SYSTEM_ID, is_active=False)
        )

        recipients = await ChatMember.active_user_ids(chat_id)

        assert sorted(recipients) == sorted([user_id, ADMIN_ID])

    async def test_unknown_chat_has_no_recipients(self, authenticated_client):
        assert await ChatMember.active_user_ids(10**9) == []

    async def test_sees_member_added_in_open_transaction(
        self, authenticated_client, db_pool
    ):
        """
        Внутри транзакции список читается ЕЁ соединением: участник, добавленный
        в этой же транзакции, попадает в адресаты (отдельное соединение пула
        незакоммиченную строку не увидело бы).
        """
        _, user_id, _ = authenticated_client
        chat_id = await Chat.create(Chat(name="Recipients tx"))

        async with ContainerTransaction(db_pool):
            await ChatMember.create(
                ChatMember(chat_id=chat_id, user_id=user_id, is_active=True)
            )
            assert await ChatMember.active_user_ids(chat_id) == [user_id]
