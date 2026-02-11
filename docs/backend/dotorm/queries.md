# Запросы

## search — поиск с фильтрами

Основной метод для получения списка записей:

```python
results = await Chat.search(
    filter=[
        ("is_archived", "=", False),
        ("chat_type", "in", ["group", "channel"]),
    ],
    fields=["id", "name", "chat_type", "creator_id"],
    order="id",
    sort="desc",
    limit=20,
    offset=0,
)
# results: list[Chat]
```

### Параметры

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `filter` | `list[tuple]` | `[]` | Фильтры `(field, operator, value)` |
| `fields` | `list[str]` | все store-поля | Какие поля загружать |
| `order` | `str` | `"id"` | Поле сортировки |
| `sort` | `str` | `"asc"` | Направление: `"asc"` / `"desc"` |
| `limit` | `int` | `None` | Максимум записей |
| `offset` | `int` | `0` | Пропустить N записей |

### Операторы фильтрации

```python
# Равенство
("status", "=", "active")
("status", "!=", "archived")

# Сравнение
("price", ">", 100)
("price", ">=", 100)
("price", "<", 1000)
("price", "<=", 1000)

# Вхождение
("chat_type", "in", ["group", "channel"])
("id", "not in", [1, 2, 3])

# Текстовый поиск
("name", "like", "%john%")
("name", "ilike", "%john%")    # case-insensitive

# NULL
("deleted_at", "=", None)
("deleted_at", "!=", None)
```

### Составные фильтры

Все условия в `filter` объединяются через `AND`:

```python
# WHERE is_active = true AND chat_type = 'group' AND name ILIKE '%test%'
await Chat.search(
    filter=[
        ("is_active", "=", True),
        ("chat_type", "=", "group"),
        ("name", "ilike", "%test%"),
    ],
)
```

## get — получение по ID

```python
# Загрузить все поля
chat = await Chat.get(1)

# Загрузить конкретные поля
chat = await Chat.get(1, fields=["name", "is_archived"])
```

!!! warning "get бросает исключение"
    Если запись не найдена, `get()` бросит исключение. Используй `get_or_none()` если запись может не существовать.

## get_or_none — безопасное получение

```python
chat = await Chat.get_or_none(999)
if chat is None:
    print("Chat not found")
```

## create — создание записи

```python
chat_id = await Chat.create(
    Chat(
        name="Development",
        chat_type="group",
        creator_id=1,
    )
)
# chat_id: int — ID созданной записи
```

### Bulk create

```python
ids = await ChatMessage.create_bulk([
    ChatMessage(chat_id=1, body="Hello", author_user_id=1),
    ChatMessage(chat_id=1, body="World", author_user_id=2),
])
# ids: list[int]
```

## update — обновление записи

```python
# Загрузить → обновить
chat = await Chat.get(1)
await chat.update(Chat(name="New Name", is_archived=True))
```

Обновляются **только заданные поля**. Поля, оставленные как `Field` (не заданные), игнорируются:

```python
# Обновит ТОЛЬКО name, остальные поля не тронуты
await chat.update(Chat(name="New Name"))
```

### Указание конкретных полей

```python
await chat.update(
    Chat(name="New", is_archived=True),
    fields=["name"],  # обновить только name, is_archived игнорируется
)
```

### Bulk update

```python
await Chat.update_bulk(
    filter=[("is_archived", "=", False)],
    values={"is_archived": True},
)
```

## delete — удаление записи

```python
chat = await Chat.get(1)
await chat.delete()
```

### Bulk delete

```python
await Chat.delete_bulk([1, 2, 3])
```

## table_len — количество записей

```python
count = await Chat.table_len()
# count: int
```

## Примеры из реального кода

### Пагинация сообщений чата

```python
async def get_messages(chat_id: int, before_id: int = None, limit: int = 50):
    filter_conditions = [
        ("chat_id", "=", chat_id),
        ("is_deleted", "=", False),
    ]

    if before_id:
        filter_conditions.append(("id", "<", before_id))

    return await env.models.chat_message.search(
        filter=filter_conditions,
        fields=["id", "body", "author_user_id", "created_at", "pinned"],
        order="id",
        sort="desc",
        limit=limit,
    )
```

### Проверка прав участника чата

```python
async def check_membership(chat_id: int, user_id: int):
    members = await env.models.chat_member.search(
        filter=[
            ("chat_id", "=", chat_id),
            ("user_id", "=", user_id),
            ("is_active", "=", True),
        ],
        fields=["id", "is_admin", "can_write", "can_pin"],
        limit=1,
    )
    return members[0] if members else None
```
