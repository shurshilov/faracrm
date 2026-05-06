# Integration Tests

## Паттерн

Каждый тест-класс:

1. `_setup()` — создаёт данные (chat, member, messages)
2. `@patch` — мокает WebSocket
3. Делает HTTP-запрос через `authenticated_client`
4. Проверяет ответ и состояние БД

```python
class TestPinMessageAPI:

    async def _setup(self, authenticated_client):
        """Создать чат, участника и сообщение."""
        client, user_id, token = authenticated_client

        from backend.base.crm.chat.models.chat import Chat
        from backend.base.crm.chat.models.chat_message import ChatMessage
        from backend.base.crm.chat.models.chat_member import ChatMember

        chat_id = await Chat.create(Chat(name="Test Chat"))
        await ChatMember.create(
            ChatMember(
                chat_id=chat_id,
                user_id=user_id,
                is_active=True,
                can_pin=True,           # (1)!
            )
        )
        msg_id = await ChatMessage.create(
            ChatMessage(
                chat_id=chat_id,
                body="Pin this",
                author_user_id=user_id,
            )
        )
        return client, chat_id, msg_id

    @patch(
        "backend.base.crm.chat.websocket.chat_manager.send_to_chat",
        new_callable=AsyncMock,
    )
    async def test_pin_message(self, mock_ws, authenticated_client):
        client, chat_id, msg_id = await self._setup(authenticated_client)

        response = await client.post(
            f"/chats/{chat_id}/messages/{msg_id}/pin",
            json={"pinned": True},
        )

        assert response.status_code == 200
        assert response.json()["pinned"] is True
        mock_ws.assert_called_once()        # (2)!
```

1. Не забудь выдать нужные права тестовому участнику.
2. Проверяй, что WebSocket-уведомление было отправлено.

## Мокирование WebSocket

`chat_manager.send_to_chat` — отправляет события через PubSub (PG LISTEN/NOTIFY или Redis). В тестах мокаем чтобы не зависеть от реальной инфраструктуры:

```python
from unittest.mock import AsyncMock, patch

@patch(
    "backend.base.crm.chat.websocket.chat_manager.send_to_chat",
    new_callable=AsyncMock,
)
async def test_send_message(self, mock_ws, authenticated_client):
    # mock_ws — AsyncMock, перехватывает вызовы send_to_chat
    ...

    # Проверка что WS-событие отправлено с правильными данными
    mock_ws.assert_called_once_with(
        chat_id=chat_id,
        message={
            "type": "new_message",
            "chat_id": chat_id,
            ...
        },
    )
```

!!! warning "Порядок аргументов с @patch"
    При использовании `@patch` как декоратора, mock передаётся **первым аргументом** после `self`:

    ```python
    # ✅ Правильно: mock_ws перед fixture
    async def test_foo(self, mock_ws, authenticated_client):

    # ❌ Неправильно: mock_ws после fixture
    async def test_foo(self, authenticated_client, mock_ws):
    ```

## Проверка состояния БД

После HTTP-запроса проверяй что данные реально изменились:

```python
@patch(...)
async def test_edit_message(self, mock_ws, authenticated_client):
    client, chat_id, msg_id, user_id = await self._setup(authenticated_client)

    response = await client.patch(
        f"/chats/{chat_id}/messages/{msg_id}",
        json={"body": "Edited text"},
    )

    assert response.status_code == 200

    # Проверяем БД напрямую
    from backend.base.crm.chat.models.chat_message import ChatMessage
    msg = await ChatMessage.get(msg_id)
    assert msg.body == "Edited text"
    assert msg.is_edited is True
```

## Типичные ошибки

### Тесты зависают

**Причина**: утечка PubSub LISTEN-соединения из пула.

**Решение**: убедись что `app` fixture вызывает `stop_services()`:

```python
@pytest_asyncio.fixture
async def app(test_env):
    ...
    yield app
    await test_env.stop_services(app)  # ← обязательно
```

### 403 в тестах

**Причина**: тестовый `ChatMember` создан без нужных прав.

**Решение**: явно указывай права:

```python
await ChatMember.create(
    ChatMember(
        chat_id=chat_id,
        user_id=user_id,
        is_active=True,
        can_write=True,    # для отправки сообщений
        can_pin=True,      # для закрепления
        is_admin=True,     # для admin-операций
    )
)
```
