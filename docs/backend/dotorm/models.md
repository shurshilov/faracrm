# Модели

Модель — это Python-класс, наследующий `DotModel`. Каждая модель соответствует одной таблице в базе данных.

## Определение модели

```python title="backend/base/crm/chat/models/chat_message.py"
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.dotorm.dotorm.fields import (
    Integer, Char, Text, Boolean, Datetime, Many2one
)


class ChatMessage(DotModel):
    __table__ = "chat_messages"       # (1)!
    __route__ = "chat_messages"       # (2)!

    chat_id = Many2one["Chat"](       # (3)!
        relation_table="chats",
        required=True,
    )
    author_user_id = Many2one["User"](
        relation_table="users",
        required=True,
    )
    body = Text()
    is_edited = Boolean(default=False)
    is_deleted = Boolean(default=False)
    pinned = Boolean(default=False)
    is_read = Boolean(default=True)
    reply_to_id = Many2one["ChatMessage"](
        relation_table="chat_messages",
    )
```

1. Имя таблицы в базе данных. Обязательное поле.
2. Имя для авто-генерированного CRUD роута (`/chat_messages/search`, `/chat_messages/create`, ...). По умолчанию равно `__table__`.
3. Внешний ключ. Генерирует колонку `chat_id INTEGER REFERENCES chats(id)`.

## Мета-атрибуты

| Атрибут | Тип | По умолчанию | Описание |
|---------|-----|-------------|----------|
| `__table__` | `str` | — | Имя таблицы в БД (обязательно) |
| `__route__` | `str` | `__table__` | Префикс REST API роута |
| `__access__` | `dict` | `{}` | Правила доступа (ACL) |

## Встроенные поля

Каждая модель автоматически получает поле `id`:

```python
class DotModel:
    id = Integer(primary_key=True)  # AUTO INCREMENT
```

!!! note "id всегда есть"
    Не нужно определять `id` в модели — он наследуется из `DotModel`.

## Регистрация модели

Модель регистрируется в `project_setup.py`:

```python title="backend/project_setup.py"
class Models(ModelsCore):
    chat = Chat
    chat_message = ChatMessage
    chat_member = ChatMember
```

После регистрации модель доступна через `env.models.chat_message` и автоматически получает:

- CRUD API роуты (`/chat_messages/search`, `/chat_messages/create`, ...)
- Pydantic-схемы валидации
- DDL для создания таблицы

## Создание экземпляра

Экземпляр модели — это **набор данных**, а не ORM-запись. Он используется как payload для `create()` и `update()`:

```python
# Payload для создания (не сохранённый в БД)
msg = ChatMessage(
    chat_id=1,
    author_user_id=42,
    body="Hello!",
)

# Сохранение → получаем id
msg_id = await ChatMessage.create(msg)

# Загрузка из БД → полноценная запись
msg = await ChatMessage.get(msg_id)
msg.body       # "Hello!"
msg.is_edited  # False (default)
msg.id         # msg_id
```

## Classmethod vs Instance

| Метод | Тип | Описание |
|-------|-----|----------|
| `Model.create(payload)` | classmethod | Создать запись |
| `Model.get(id)` | classmethod | Получить по ID |
| `Model.search(...)` | classmethod | Поиск с фильтрами |
| `record.update(payload)` | instance | Обновить запись |
| `record.delete()` | instance | Удалить запись |

```python
# Classmethod — вызывается на классе
chat = await Chat.get(1)
chats = await Chat.search(filter=[("is_archived", "=", False)])

# Instance — вызывается на загруженной записи
await chat.update(Chat(name="New name"))
await chat.delete()
```

## DDL — автоматическое создание таблиц

При первом запуске DotORM автоматически создаёт таблицы:

```python
# Вызывается один раз при старте
async with ContainerTransaction(pool) as session:
    for model in all_models:
        foreign_keys = await model.__create_table__(session)
```

Генерируемый SQL:

```sql
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id),
    author_user_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT,
    is_edited BOOLEAN DEFAULT false,
    is_deleted BOOLEAN DEFAULT false,
    pinned BOOLEAN DEFAULT false,
    is_read BOOLEAN DEFAULT true,
    reply_to_id INTEGER REFERENCES chat_messages(id)
);
```
