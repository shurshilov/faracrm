# DotORM

Async ORM for PostgreSQL, MySQL, Clickhouse, developed specifically for FARA CRM.

## Why a custom ORM?

- **Fully async** — native asyncpg support, no sync wrappers
- **Auto-generated CRUD API** — model → REST API with zero code
- **Declarative relations** — Many2one, One2many, Many2many with automatic JOIN
- **Auto-generated DDL** — `CREATE TABLE` from model definition
- **Access Control** — built-in permission checks at the ORM level

## Quick example

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
# Create
chat_id = await Chat.create(Chat(name="General", creator_id=1))
# or better
chat_id = await Chat.create(Chat(name="General", creator_id=User(id=1)))

# Read
chat = await Chat.get(chat_id)
chat = await Chat.get(chat_id, fields=["name", "is_archived"])
# or if you need nested fields in one query
chat = await Chat.get(chat_id,
    fields=["name", "is_archived"],
    nested_fields={"creator_id": ["name", "id"]},
)

# Search
chats = await Chat.search(
    filter=[("is_archived", "=", False)],
    fields=["id", "name"],
    order="id",
    sort="desc",
    limit=20,
)

# Update
await chat.update(Chat(name="New Name"))

# Delete
await chat.delete()
```

## Sections

- [Models](models.md) — defining models, `DotModel`, `__table__`
- [Fields](fields.md) — field types, parameters, defaults
- [Queries](queries.md) — `search`, `get`, `create`, `update`, `delete`
- [Relations](relations.md) — Many2one, One2many, Many2many
- [CRUD Auto](crud-auto.md) — REST API auto-generation
