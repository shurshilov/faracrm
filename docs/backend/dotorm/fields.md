# Поля (Fields)

Поля определяют типы колонок и их поведение. Каждое поле — это дескриптор Python, который управляет валидацией, сериализацией и DDL-генерацией.

## Скалярные поля

### Integer / BigInteger / SmallInteger

```python
from backend.base.system.dotorm.dotorm.fields import (
    Integer, BigInteger, SmallInteger
)

class Product(DotModel):
    __table__ = "products"

    quantity = Integer(default=0)
    price_cents = BigInteger()
    sort_order = SmallInteger(default=0)
```

| Поле | PostgreSQL | Python |
|------|-----------|--------|
| `Integer` | `INTEGER` | `int` |
| `BigInteger` | `BIGINT` | `int` |
| `SmallInteger` | `SMALLINT` | `int` |

### Char / Text

```python
from backend.base.system.dotorm.dotorm.fields import Char, Text

class User(DotModel):
    __table__ = "users"

    name: str = Char(max_length=255, required=True)   # VARCHAR(255) NOT NULL
    login: str = Char(max_length=100, unique=True)     # VARCHAR(100) UNIQUE
    bio: str = Text()                                   # TEXT
```

### Boolean

```python
is_active = Boolean(default=True)     # BOOLEAN DEFAULT true
is_deleted = Boolean(default=False)
```

### Datetime / Date / Time

```python
from backend.base.system.dotorm.dotorm.fields import Datetime, Date, Time

class Task(DotModel):
    __table__ = "tasks"

    due_date = Date()                              # DATE
    reminder_time = Time()                         # TIME
    created_at = Datetime(default="now")           # TIMESTAMPTZ DEFAULT now()
    updated_at = Datetime(default="now")
```

### Float / Decimal

```python
from backend.base.system.dotorm.dotorm.fields import Float, Decimal

weight = Float()                                   # FLOAT
price = Decimal(precision=10, scale=2)             # NUMERIC(10, 2)
```

### JSONField

```python
from backend.base.system.dotorm.dotorm.fields import JSONField

metadata = JSONField(default={})      # JSONB DEFAULT '{}'
tags = JSONField(default=[])          # JSONB DEFAULT '[]'
```

!!! tip "asyncpg и JSONB"
    asyncpg не десериализует JSONB автоматически. DotORM делает `json.loads()` при чтении, если значение пришло строкой.

### Selection

Поле с ограниченным набором значений:

```python
from backend.base.system.dotorm.dotorm.fields import Selection

class Chat(DotModel):
    __table__ = "chats"

    chat_type = Selection(
        selection=[
            ("direct", "Личный"),
            ("group", "Группа"),
            ("channel", "Канал"),
            ("record", "Чат записи"),
        ],
        default="group",
        required=True,
    )
```

В PostgreSQL это `VARCHAR` с валидацией на уровне ORM. Значения хранятся как строки (`"direct"`, `"group"`, ...).

## Параметры полей

Все поля наследуют общие параметры от базового `Field`:

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `required` | `bool` | `False` | `NOT NULL` в DDL |
| `default` | `any` | `None` | Значение по умолчанию |
| `unique` | `bool` | `False` | `UNIQUE` constraint |
| `index` | `bool` | `False` | Создать индекс |
| `store` | `bool` | `True` | Хранить в БД (False для computed) |
| `readonly` | `bool` | `False` | Не обновлять через API |

```python
name = Char(
    max_length=255,
    required=True,       # NOT NULL
    unique=True,         # UNIQUE
    index=True,          # CREATE INDEX
)

created_at = Datetime(
    default="now",
    readonly=True,       # нельзя изменить через API
)
```

## Поля связей

### Many2one (FK)

Внешний ключ — ссылка на одну запись другой таблицы:

```python
from backend.base.system.dotorm.dotorm.fields import Many2one

class ChatMessage(DotModel):
    __table__ = "chat_messages"

    # FK → chats.id
    chat_id = Many2one["Chat"](
        relation_table="chats",
        required=True,
    )

    # FK → users.id (nullable)
    author_user_id = Many2one["User"](
        relation_table="users",
    )
```

При чтении:

```python
msg = await ChatMessage.get(1)
msg.chat_id       # int (FK value) — при обычном чтении
msg.chat_id.name  # str — при чтении с nested fields
```

### One2many

Обратная связь — список дочерних записей:

```python
from backend.base.system.dotorm.dotorm.fields import One2many

class Chat(DotModel):
    __table__ = "chats"

    messages = One2many["ChatMessage"](
        relation_table="chat_messages",      # таблица дочерних записей
        relation_table_field="chat_id",      # FK в дочерней таблице
    )
```

!!! note "One2many не создаёт колонку"
    `One2many` — виртуальное поле. Оно не генерирует колонку в БД, а только определяет связь для чтения.

### Many2many

Связь многие-ко-многим через промежуточную таблицу:

```python
from backend.base.system.dotorm.dotorm.fields import Many2many

class User(DotModel):
    __table__ = "users"

    role_ids = Many2many["Role"](
        relation_table="roles",              # целевая таблица
        many2many_table="user_roles",        # промежуточная таблица
        column1="user_id",                   # FK на текущую модель
        column2="role_id",                   # FK на целевую модель
    )
```

Промежуточная таблица создаётся автоматически:

```sql
CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER REFERENCES users(id),
    role_id INTEGER REFERENCES roles(id),
    PRIMARY KEY (user_id, role_id)
);
```

### One2one

Связь один-к-одному:

```python
from backend.base.system.dotorm.dotorm.fields import One2one

class User(DotModel):
    __table__ = "users"

    profile = One2one["UserProfile"](
        relation_table="user_profiles",
        relation_table_field="user_id",
    )
```
