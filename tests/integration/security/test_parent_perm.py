"""
parent_perm у parent-операторов правил: что требовать от родителя.

До этого @has_parent_access и @has_polymorphic_parent_access всегда
спрашивали у родителя ЧТЕНИЕ, какое бы действие ни делали с дочерней
записью, а флаги perm_* правил раздавали по этому ответу create/delete:

- реакции: читатель из команды (видит чат, писать не может) ставил реакции
  и снимал чужие; участник снимал чужие и ставил от чужого имени;
- вложения: кто видит родителя — правил его файлы; правил на delete не было
  вовсе, и ACL базовой роли удалял любую строку по id, даже невидимую
  (DELETE /attachment/bulk с перебором id).

Теперь правило отвечает на оба вопроса: perms — действие над дочерней
записью, parent_perm — какой флаг нужен на родителе. Люди здесь:

- alice, bob — участники чата (пишут);
- carol — в команде чата, но не участник (только читает);
- dave — посторонний.

Как в test_security_rules: настоящие роли и правила (post_init из
conftest), доступ через ORM под сессией пользователя (as_user), состояние
базы проверяется SQL-запросом мимо ORM.

Run: pytest tests/integration/security/test_parent_perm.py -v -m integration
"""

from types import SimpleNamespace

import pytest
import pytest_asyncio

from backend.base.crm.attachments.models.attachments import Attachment
from backend.base.crm.chat.models.chat import Chat
from backend.base.crm.chat.models.chat_member import ChatMember
from backend.base.crm.chat.models.chat_message import ChatMessage
from backend.base.crm.chat.models.chat_message_reaction import (
    ChatMessageReaction,
)
from backend.base.crm.leads.models.team_crm import TeamCrm
from backend.base.system.dotorm.dotorm.access import AccessDenied
from backend.base.system.dotorm.dotorm.databases.postgres.transaction import (
    ContainerTransaction,
)
from tests.integration.security.test_field_access import _role_id, as_user

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def sales(user_factory, db_pool):
    """Чат отдела продаж: alice и bob участники, carol читает по команде,
    dave посторонний; одно сообщение alice."""
    base_user = await _role_id("base_user")
    people = {}
    for login in ("alice", "bob", "carol", "dave"):
        people[login] = await user_factory(
            name=login.capitalize(),
            login=login,
            role_ids={"selected": [base_user]},
        )
    team_id = await TeamCrm.create(TeamCrm(name="Продажи"))
    await db_pool.execute(
        "INSERT INTO team_crm_user_many2many (user_id, team_id) "
        "VALUES ($1, $2)",
        people["carol"].id,
        team_id,
    )
    chat_id = await Chat.create(Chat(name="Отдел продаж", team_id=team_id))
    for login in ("alice", "bob"):
        await ChatMember.create(
            ChatMember(
                chat_id=chat_id, user_id=people[login].id, is_active=True
            )
        )
    message_id = await ChatMessage.create(
        ChatMessage(
            chat_id=chat_id,
            body="Отчёт готов",
            author_user_id=people["alice"].id,
        )
    )
    return SimpleNamespace(chat_id=chat_id, message_id=message_id, **people)


@pytest_asyncio.fixture
async def report(sales):
    """Файл под сообщением alice (создан системой, как загрузка в чат)."""
    return await Attachment.create(
        Attachment(
            name="report.pdf",
            mimetype="application/pdf",
            size=200,
            res_model="chat_message",
            res_id=sales.message_id,
        )
    )


async def _exists(db_pool, model, record_id: int) -> bool:
    """Строка на месте — SQL мимо ORM, таблица из модели (attachments!)."""
    return bool(
        await db_pool.fetchval(
            f'SELECT count(*) FROM "{model.__table__}" WHERE id = $1',
            record_id,
        )
    )


def _reaction(message_id: int, user_id: int) -> ChatMessageReaction:
    return ChatMessageReaction(
        emoji="👍", message_id=message_id, user_id=user_id
    )


async def _react(user, message_id: int) -> int:
    """Реакция пользователя под его же сессией — как ручка чата."""
    async with as_user(user):
        return await ChatMessageReaction.create(_reaction(message_id, user.id))


class TestReactions:
    async def test_team_reader_sees_message_but_cannot_react(
        self, sales, db_pool
    ):
        """Carol видит сообщение (чат её команды), но писать в чат не может:
        create-правило требует update на сообщении. INSERT откатывается
        транзакцией, как в роуте автокруда."""
        async with as_user(sales.carol):
            assert (
                await ChatMessage.search_count(
                    filter=[("id", "=", sales.message_id)]
                )
                == 1
            )
            with pytest.raises(AccessDenied):
                async with ContainerTransaction(db_pool):
                    await ChatMessageReaction.create(
                        _reaction(sales.message_id, sales.carol.id)
                    )
        assert (
            await db_pool.fetchval(
                f'SELECT count(*) FROM "{ChatMessageReaction.__table__}"'
            )
            == 0
        )

    async def test_member_cannot_react_on_behalf_of_another(
        self, sales, db_pool
    ):
        """Реакция только своя: user_id = {{user_id}} в create-правиле."""
        async with as_user(sales.bob):
            with pytest.raises(AccessDenied):
                async with ContainerTransaction(db_pool):
                    await ChatMessageReaction.create(
                        _reaction(sales.message_id, sales.alice.id)
                    )
        assert (
            await db_pool.fetchval(
                f'SELECT count(*) FROM "{ChatMessageReaction.__table__}"'
            )
            == 0
        )

    async def test_member_cannot_remove_others_reaction(self, sales, db_pool):
        reaction_id = await _react(sales.alice, sales.message_id)

        async with as_user(sales.bob):
            reaction = await ChatMessageReaction.get(reaction_id)
            with pytest.raises(AccessDenied):
                await reaction.delete()
            with pytest.raises(AccessDenied):
                await ChatMessageReaction.delete_bulk([reaction_id])
        assert await _exists(db_pool, ChatMessageReaction, reaction_id)

    async def test_member_removes_own_reaction(self, sales, db_pool):
        reaction_id = await _react(sales.bob, sales.message_id)

        async with as_user(sales.bob):
            reaction = await ChatMessageReaction.get(reaction_id)
            await reaction.delete()
        assert not await _exists(db_pool, ChatMessageReaction, reaction_id)


class TestAttachments:
    async def test_reader_sees_file_but_cannot_change_it(
        self, sales, report, db_pool
    ):
        """Carol видит файл (видит сообщение), но менять сообщение не может,
        значит и его файлы: ни переименовать, ни удалить."""
        async with as_user(sales.carol):
            attachment = await Attachment.get(report)
            with pytest.raises(AccessDenied):
                await attachment.update(payload=Attachment(name="renamed.pdf"))
            with pytest.raises(AccessDenied):
                await attachment.delete()
        row = await db_pool.fetchrow(
            f'SELECT name FROM "{Attachment.__table__}" WHERE id = $1', report
        )
        assert row["name"] == "report.pdf"

    async def test_outsider_cannot_delete_blind(self, sales, report, db_pool):
        """Dave файла не видит. Раньше delete_bulk по списку id удалял строку
        без единой проверки: ACL базовой роли FULL, правил на delete нет."""
        async with as_user(sales.dave):
            assert (
                await Attachment.search_count(filter=[("id", "=", report)])
                == 0
            )
            with pytest.raises(AccessDenied):
                await Attachment.delete_bulk([report])
        assert await _exists(db_pool, Attachment, report)

    async def test_member_manages_files_of_writable_message(
        self, sales, report, db_pool
    ):
        async with as_user(sales.bob):
            attachment = await Attachment.get(report)
            await attachment.update(payload=Attachment(name="renamed.pdf"))
            await attachment.delete()
        assert not await _exists(db_pool, Attachment, report)

    async def test_uploader_removes_own_file(self, sales, db_pool):
        """Свой файл удаляется и там, где менять родителя нельзя."""
        async with as_user(sales.carol):
            own = await Attachment.create(
                Attachment(
                    name="note.txt",
                    mimetype="text/plain",
                    size=5,
                    res_model="chat_message",
                    res_id=sales.message_id,
                )
            )
            attachment = await Attachment.get(own)
            await attachment.delete()
        assert not await _exists(db_pool, Attachment, own)
