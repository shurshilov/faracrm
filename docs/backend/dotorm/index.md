# DotORM

Асинхронный ORM для PostgreSQL, Mysql, Clickhouse, разработанный специально для FARA CRM.

## Почему свой ORM?

- **Полный async** — нативная работа с asyncpg, без sync-обёрток
- **Автогенерация CRUD API** — модель → REST API за 0 строк кода
- **Декларативные связи** — Many2one, One2many, Many2many с автоматическим JOIN
- **Автогенерация DDL** — `CREATE TABLE` из определения модели
- **Access Control** — встроенная проверка прав на уровне ORM

## Быстрый пример

```python
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.dotorm.dotorm.fields import (
    Char, Text, Boolean, Many2one, One2many
)


class Chat(DotModel):
    __table__ = "chats"

    name: str = Char(max_length=255, required=True)
    description: str = Text()
    is_archived: bool = Boolean(default=False)
    creator_id: "User" = Many2one["User"](
        relation_table="users",
        required=True,
    )
    messages: list["ChatMessage"] = One2many["ChatMessage"](
        relation_table="chat_messages",
        relation_table_field="chat_id",
    )
```

```python
# Создание
chat_id = await Chat.create(Chat(name="General", creator_id=1))
# или что лучше
chat_id = await Chat.create(Chat(name="General", creator_id=User(id=1)))

# Чтение
chat = await Chat.get(chat_id)
chat = await Chat.get(chat_id, fields=["name", "is_archived"])
# или если нужны вложенные поля за запрос то
chat = await Chat.get(chat_id,
    fields=["name", "is_archived"], 
    nested_fields={"creator_id":["name", "id"]}
    )

# Поиск
chats = await Chat.search(
    filter=[("is_archived", "=", False)],
    fields=["id", "name"],
    order="id",
    sort="desc",
    limit=20,
)

# Обновление
await chat.update(Chat(name="New Name"))

# Удаление
await chat.delete()
```

## Разделы

- [Модели](models.md) — определение моделей, `DotModel`, `__table__`
- [Поля](fields.md) — типы полей, параметры, значения по умолчанию
- [Запросы](queries.md) — `search`, `get`, `create`, `update`, `delete`
- [Связи](relations.md) — Many2one, One2many, Many2many
- [CRUD Auto](crud-auto.md) — автогенерация REST API
