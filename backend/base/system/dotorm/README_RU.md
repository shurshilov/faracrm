<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT">
  <img src="https://img.shields.io/badge/coverage-87%25-brightgreen.svg" alt="Coverage 87%">
  <img src="https://img.shields.io/badge/version-2.0.0-orange.svg" alt="Version 2.0.0">
</p>

<h1 align="center">🚀 DotORM</h1>

<p align="center">
  <b>Высокопроизводительный асинхронный ORM для Python с поддержкой PostgreSQL, MySQL и ClickHouse</b>
</p>

<p align="center">
  <i>Простой, быстрый, type-safe</i>
</p>

---

## 📋 Содержание

- [✨ Особенности](#-особенности)
- [📦 Установка](#-установка)
- [🚀 Быстрый старт](#-быстрый-старт)
- [📖 Примеры использования](#-примеры-использования)
- [⚡ Решение проблемы N+1](#-решение-проблемы-n1)
- [📊 Бенчмарки](#-бенчмарки)
- [🏗️ Архитектура](#️-архитектура)
- [🧪 Тестирование](#-тестирование)
- [📚 API Reference](#-api-reference)
- [👤 Автор](#-автор)
- [📄 Лицензия](#-лицензия)

---

## ✨ Особенности

| Возможность | Описание |
|-------------|----------|
| 🔄 **Асинхронность** | Полностью async/await на базе asyncpg, aiomysql, asynch |
| 🎯 **Type Safety** | Полная поддержка типов Python 3.12+ с generics |
| 🔗 **Отношения** | Many2One, One2Many, Many2Many, One2One |
| 🛡️ **Безопасность** | Параметризованные запросы, защита от SQL-инъекций |
| 📦 **Batch операции** | Оптимизированные bulk create/update/delete |
| 🚫 **Решение N+1** | Встроенная оптимизация загрузки связей |
| 🔌 **Multi-DB** | PostgreSQL, MySQL, ClickHouse |
| 🏭 **DDL** | Автоматическое создание и миграция таблиц |

---

## 📦 Установка

```bash
# Базовая установка
pip install dotorm

# С поддержкой PostgreSQL
pip install dotorm[postgres]

# С поддержкой MySQL
pip install dotorm[mysql]

# С поддержкой ClickHouse
pip install dotorm[clickhouse]

# Все драйверы
pip install dotorm[all]
```

### Зависимости

```txt
# requirements.txt
asyncpg>=0.29.0      # PostgreSQL
aiomysql>=0.2.0      # MySQL
asynch>=0.2.3        # ClickHouse
pydantic>=2.0.0      # Валидация
```

---

## 🚀 Быстрый старт

### 1. Определение модели

```python
from dotorm import DotModel, Integer, Char, Boolean, Many2one, One2many
from dotorm.components import POSTGRES

class Role(DotModel):
    __table__ = "roles"
    _dialect = POSTGRES

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=100, required=True)
    description: str = Char(max_length=255)

class User(DotModel):
    __table__ = "users"
    _dialect = POSTGRES

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=100, required=True)
    email: str = Char(max_length=255, unique=True)
    active: bool = Boolean(default=True)
    role_id: Role = Many2one(lambda: Role)

class Role(DotModel):
    # ... поля выше ...
    users: list[User] = One2many(lambda: User, "role_id")
```

### 2. Подключение к базе данных

```python
from dotorm.databases.postgres import ContainerPostgres
from dotorm.databases.abstract import PostgresPoolSettings, ContainerSettings

# Настройки подключения
pool_settings = PostgresPoolSettings(
    host="localhost",
    port=5432,
    user="postgres",
    password="password",
    database="myapp"
)

container_settings = ContainerSettings(
    driver="asyncpg",
    reconnect_timeout=10
)

# Создание пула соединений
container = ContainerPostgres(pool_settings, container_settings)
pool = await container.create_pool()

# Привязка пула к моделям
User._pool = pool
User._no_transaction = container.get_no_transaction_session()
Role._pool = pool
Role._no_transaction = container.get_no_transaction_session()
```

### 3. Создание таблиц

```python
# Автоматическое создание таблиц с FK
await container.create_and_update_tables([Role, User])
```

> **Примечание.** SQL-билдер, кэш полей и таблицы триггеров `@depends`
> строятся **автоматически** при определении класса модели — ручная проводка
> не нужна. Достаточно привязать `_pool` / `_no_transaction`, как выше.

### Контроль доступа (опционально)

По умолчанию DotORM **пермиссивен** — CRUD работает из коробки, **сессия не
нужна**. Контроль доступа **включается по желанию**: установите чекер, у
которого `require_session = True`, и DotORM переходит в **default-deny** —
тогда каждая CRUD-операция требует сессию в контексте, иначе `AccessDenied`
(так работает FARA CRM — защита от забытой проверки авторизации, сливающей
данные).

```python
from dotorm import (
    set_access_checker, set_access_session, SystemSession, AccessChecker,
)

class MyChecker(AccessChecker):
    require_session = True          # включить default-deny
    # переопределите check_access() / check_field_access() своей политикой

set_access_checker(MyChecker())
set_access_session(SystemSession())   # сессия полного доступа
```

Сессия хранится в `contextvars.ContextVar`, поэтому ставьте её **на каждый
запрос / задачу / поток** — в async-коде, который порождает задачи, ставьте её
в начале каждой задачи (contextvars не переходят между задачами автоматически).
Готовые `SystemSession` (полный доступ) и `AnonymousSession` (публичная, без
пользователя) — из коробки; ваш чекер читает то, что несёт сессия (user_id,
роли, тенант).

---

## 📖 Примеры использования

### CRUD операции

```python
# ═══════════════════════════════════════════════════════════
# CREATE - Создание записей
# ═══════════════════════════════════════════════════════════

# Одиночное создание
user = User(name="Артём", email="artem@example.com", role_id=1)
user_id = await User.create(user)
print(f"Created user with ID: {user_id}")

# Массовое создание (bulk)
users = [
    User(name="Иван", email="ivan@example.com"),
    User(name="Мария", email="maria@example.com"),
    User(name="Пётр", email="petr@example.com"),
]
created_ids = await User.create_bulk(users)
print(f"Created {len(created_ids)} users")

# ═══════════════════════════════════════════════════════════
# READ - Чтение записей
# ═══════════════════════════════════════════════════════════

# Получение по ID
user = await User.get(1)
print(f"User: {user.name}")

# Получение с выбором полей
user = await User.get(1, fields=["id", "name", "email"])

# Поиск с фильтрацией
active_users = await User.search(
    fields=["id", "name", "email"],
    filter=[("active", "=", True)],
    order="ASC",
    sort="name",
    limit=10
)

# Сложные фильтры
users = await User.search(
    fields=["id", "name"],
    filter=[
        ("active", "=", True),
        "and",
        [
            ("name", "ilike", "арт"),
            "or",
            ("email", "like", "@gmail.com")
        ]
    ]
)

# Пагинация
page_1 = await User.search(fields=["id", "name"], start=0, end=20)
page_2 = await User.search(fields=["id", "name"], start=20, end=40)

# ═══════════════════════════════════════════════════════════
# UPDATE - Обновление записей
# ═══════════════════════════════════════════════════════════

# Обновление одной записи
user = await User.get(1)
user.name = "Новое имя"
await user.update()

# Обновление с payload
user = await User.get(1)
payload = User(name="Обновлённое имя", active=False)
await user.update(payload, fields=["name", "active"])

# Массовое обновление
await User.update_bulk(
    ids=[1, 2, 3],
    payload=User(active=False)
)

# ═══════════════════════════════════════════════════════════
# DELETE - Удаление записей
# ═══════════════════════════════════════════════════════════

# Удаление одной записи
user = await User.get(1)
await user.delete()

# Массовое удаление
await User.delete_bulk([4, 5, 6])
```

### Работа с отношениями

```python
# ═══════════════════════════════════════════════════════════
# Many2One - Многие к одному
# ═══════════════════════════════════════════════════════════

# Получение пользователя с ролью
user = await User.get_with_relations(
    id=1,
    fields=["id", "name", "role_id"]
)
print(f"User: {user.name}, Role: {user.role_id.name}")

# ═══════════════════════════════════════════════════════════
# One2Many - Один ко многим
# ═══════════════════════════════════════════════════════════

# Получение роли со всеми пользователями
role = await Role.get_with_relations(
    id=1,
    fields=["id", "name", "users"],
    fields_info={"users": ["id", "name", "email"]}
)
print(f"Role: {role.name}")
for user in role.users["data"]:
    print(f"  - {user.name}")

# ═══════════════════════════════════════════════════════════
# Many2Many - Многие ко многим
# ═══════════════════════════════════════════════════════════

class Tag(DotModel):
    __table__ = "tags"
    _dialect = POSTGRES

    id: int = Integer(primary_key=True)
    name: str = Char(max_length=50)

class Article(DotModel):
    __table__ = "articles"
    _dialect = POSTGRES

    id: int = Integer(primary_key=True)
    title: str = Char(max_length=200)
    tags: list[Tag] = Many2many(
        relation_table=lambda: Tag,
        many2many_table="article_tags",
        column1="tag_id",
        column2="article_id"
    )

# Получение статьи с тегами
article = await Article.get_with_relations(
    id=1,
    fields=["id", "title", "tags"]
)

# Добавление тегов к статье
await Article.link_many2many(
    field=Article.tags,
    values=[(article.id, 1), (article.id, 2), (article.id, 3)]
)

# Удаление тегов
await Article.unlink_many2many(
    field=Article.tags,
    ids=[1, 2]
)
```

### Транзакции

```python
from dotorm.databases.postgres import ContainerTransaction

async with ContainerTransaction(pool) as session:
    # Все операции в одной транзакции
    role_id = await Role.create(
        Role(name="Admin"),
        session=session
    )
    
    user_id = await User.create(
        User(name="Admin User", role_id=role_id),
        session=session
    )
    
    # Автоматический commit при выходе
    # Автоматический rollback при исключении
```

### Фильтры

```python
# ═══════════════════════════════════════════════════════════
# Поддерживаемые операторы
# ═══════════════════════════════════════════════════════════

# Сравнение
filter=[("age", "=", 25)]
filter=[("age", "!=", 25)]
filter=[("age", ">", 18)]
filter=[("age", ">=", 18)]
filter=[("age", "<", 65)]
filter=[("age", "<=", 65)]

# Поиск по строке
filter=[("name", "like", "John")]      # %John%
filter=[("name", "ilike", "john")]     # case-insensitive
filter=[("name", "not like", "test")]

# IN / NOT IN
filter=[("status", "in", ["active", "pending"])]
filter=[("id", "not in", [1, 2, 3])]

# NULL проверки
filter=[("deleted_at", "is null", None)]
filter=[("email", "is not null", None)]

# BETWEEN
filter=[("created_at", "between", ["2024-01-01", "2024-12-31"])]

# ═══════════════════════════════════════════════════════════
# Логические операторы
# ═══════════════════════════════════════════════════════════

# AND (по умолчанию между условиями)
filter=[
    ("active", "=", True),
    ("verified", "=", True)
]

# OR
filter=[
    ("role", "=", "admin"),
    "or",
    ("role", "=", "moderator")
]

# Вложенные условия
filter=[
    ("active", "=", True),
    "and",
    [
        ("role", "=", "admin"),
        "or",
        ("role", "=", "superuser")
    ]
]

# NOT
filter=[
    ("not", ("deleted", "=", True))
]
```

---

## ⚡ Решение проблемы N+1

### Проблема N+1

```python
# ❌ ПЛОХО: N+1 запросов
users = await User.search(fields=["id", "name", "role_id"], limit=100)
for user in users:
    # Каждый вызов = новый запрос к БД!
    role = await Role.get(user.role_id)
    print(f"{user.name} - {role.name}")
# Итого: 1 + 100 = 101 запрос!
```

### Решение в DotORM

#### 1. Автоматическая загрузка связей в search()

```python
# ✅ ХОРОШО: 2 запроса вместо 101
users = await User.search(
    fields=["id", "name", "role_id"],  # role_id - это Many2one
    limit=100
)
# DotORM автоматически:
# 1. Загружает всех users (1 запрос)
# 2. Собирает уникальные role_id
# 3. Загружает все роли одним запросом (1 запрос)
# 4. Маппит роли на пользователей в памяти

for user in users:
    print(f"{user.name} - {user.role_id.name}")  # Без дополнительных запросов!
```

#### 2. Batch загрузка Many2Many

```python
# ✅ ХОРОШО: Оптимизированная загрузка M2M
articles = await Article.search(
    fields=["id", "title", "tags"],
    limit=50
)
# DotORM выполняет:
# 1. SELECT * FROM articles LIMIT 50
# 2. SELECT tags.*, article_tags.article_id as m2m_id
#    FROM tags
#    JOIN article_tags ON tags.id = article_tags.tag_id
#    WHERE article_tags.article_id IN (1, 2, 3, ..., 50)
# Всего 2 запроса!
```

#### 3. Batch загрузка One2Many

```python
# ✅ ХОРОШО: Оптимизированная загрузка O2M
roles = await Role.search(
    fields=["id", "name", "users"],
    limit=10
)
# DotORM выполняет:
# 1. SELECT * FROM roles LIMIT 10
# 2. SELECT * FROM users WHERE role_id IN (1, 2, 3, ..., 10)
# Всего 2 запроса!
```

### Архитектура решения N+1

```
┌─────────────────────────────────────────────────────────────┐
│                      ORM Layer                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  search() method                      │    │
│  │  1. Execute main query                               │    │
│  │  2. Collect relation field IDs                       │    │
│  │  3. Call _records_list_get_relation()               │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         _records_list_get_relation()                 │    │
│  │  1. Build optimized queries for all relation types   │    │
│  │  2. Execute queries in parallel (asyncio.gather)    │    │
│  │  3. Map results back to parent records              │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Builder Layer                           │    │
│  │  build_search_relation() - builds batch queries      │    │
│  │  ┌─────────────┬─────────────┬─────────────┐        │    │
│  │  │   Many2One  │  One2Many   │  Many2Many  │        │    │
│  │  │  IN clause  │  IN clause  │  JOIN query │        │    │
│  │  └─────────────┴─────────────┴─────────────┘        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Сравнение количества запросов

| Сценарий | Наивный подход | DotORM |
|----------|----------------|--------|
| 100 users + roles (M2O) | 101 запросов | 2 запроса |
| 50 articles + tags (M2M) | 51 запрос | 2 запроса |
| 10 roles + users (O2M) | 11 запросов | 2 запроса |
| Комбинированный | 162 запроса | 4 запроса |

---

## 📊 Бенчмарки

### Методология тестирования

- **Hardware**: AMD Ryzen 7 5800X, 32GB RAM, NVMe SSD
- **Database**: PostgreSQL 16, локально
- **Python**: 3.12.0
- **Данные**: 100,000 записей в таблице users
- **Измерения**: среднее из 100 итераций

### Сравнение с другими ORM

#### INSERT (1000 записей)

| ORM | Время (мс) | Запросов | Относительно |
|-----|------------|----------|--------------|
| **DotORM** | **45** | **1** | **1.0x** |
| SQLAlchemy 2.0 | 120 | 1000 | 2.7x |
| Tortoise ORM | 89 | 1 | 2.0x |
| databases + raw SQL | 42 | 1 | 0.9x |

```python
# DotORM - bulk insert
users = [User(name=f"User {i}", email=f"user{i}@test.com") for i in range(1000)]
await User.create_bulk(users)  # 1 запрос
```

#### SELECT (1000 записей)

| ORM | Время (мс) | Память (MB) | Относительно |
|-----|------------|-------------|--------------|
| **DotORM** | **12** | **8.2** | **1.0x** |
| SQLAlchemy 2.0 | 28 | 15.4 | 2.3x |
| Tortoise ORM | 22 | 12.1 | 1.8x |
| databases + raw SQL | 10 | 6.5 | 0.8x |

#### SELECT с JOIN (M2O, 1000 записей)

| ORM | Время (мс) | Запросов | Относительно |
|-----|------------|----------|--------------|
| **DotORM** | **18** | **2** | **1.0x** |
| SQLAlchemy (lazy) | 1250 | 1001 | 69x |
| SQLAlchemy (eager) | 35 | 1 | 1.9x |
| Tortoise ORM | 45 | 2 | 2.5x |

#### UPDATE (1000 записей)

| ORM | Время (мс) | Запросов | Относительно |
|-----|------------|----------|--------------|
| **DotORM** | **38** | **1** | **1.0x** |
| SQLAlchemy 2.0 | 95 | 1000 | 2.5x |
| Tortoise ORM | 78 | 1 | 2.1x |

### График производительности

```
INSERT 1000 records (lower is better)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DotORM          ████████████░░░░░░░░░░░░░░░░░░░░  45ms
Tortoise        ██████████████████████████░░░░░░  89ms
SQLAlchemy      ████████████████████████████████ 120ms

SELECT 1000 records with M2O relation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DotORM          ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░  18ms (2 queries)
SQLAlchemy eager████████░░░░░░░░░░░░░░░░░░░░░░░░  35ms (1 query)
Tortoise        ██████████░░░░░░░░░░░░░░░░░░░░░░  45ms (2 queries)
SQLAlchemy lazy ████████████████████████████████ 1250ms (1001 queries)
```

### Запуск бенчмарков

```bash
# Установка зависимостей для бенчмарков
pip install pytest-benchmark memory_profiler

# Запуск всех бенчмарков
python -m pytest benchmarks/ -v --benchmark-only

# Запуск конкретного бенчмарка
python -m pytest benchmarks/test_insert.py -v

# С профилированием памяти
python -m memory_profiler benchmarks/memory_test.py
```

---

## 🏗️ Архитектура

### Общая архитектура

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Application Layer                              │
│                    (FastAPI, Django, Flask, etc.)                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              DotORM                                      │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │                         Model Layer                             │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │     │
│  │  │   DotModel   │  │    Fields    │  │   Pydantic   │          │     │
│  │  │  (Base ORM)  │  │  (Type Def)  │  │ (Validation) │          │     │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │                          ORM Layer                              │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │     │
│  │  │ PrimaryMixin │  │ Many2Many    │  │  Relations   │          │     │
│  │  │  (CRUD ops)  │  │    Mixin     │  │    Mixin     │          │     │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │     │
│  │  ┌──────────────┐                                               │     │
│  │  │   DDLMixin   │                                               │     │
│  │  │(Table mgmt)  │                                               │     │
│  │  └──────────────┘                                               │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │                        Builder Layer                            │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │     │
│  │  │  CRUDMixin   │  │  M2MMixin    │  │ RelationsMix │          │     │
│  │  │ (SQL CRUD)   │  │  (M2M SQL)   │  │  (Batch SQL) │          │     │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │     │
│  │  ┌──────────────┐  ┌──────────────┐                             │     │
│  │  │ FilterParser │  │   Dialect    │                             │     │
│  │  │(WHERE build) │  │  (DB adapt)  │                             │     │
│  │  └──────────────┘  └──────────────┘                             │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │                       Database Layer                            │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │     │
│  │  │  PostgreSQL  │  │    MySQL     │  │  ClickHouse  │          │     │
│  │  │   asyncpg    │  │   aiomysql   │  │    asynch    │          │     │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │     │
│  └────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

### Архитектура ORM Layer

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            ORM Layer                                     │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                         DotModel                                  │    │
│  │                    (Main Model Class)                            │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │ Class Variables:                                         │    │    │
│  │  │  • __table__: str          - Table name                  │    │    │
│  │  │  • _pool: Pool             - Connection pool             │    │    │
│  │  │  • _dialect: Dialect       - Database dialect            │    │    │
│  │  │  • _builder: Builder       - SQL builder instance        │    │    │
│  │  │  • _no_transaction: Type   - Session factory             │    │    │
│  │  └─────────────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │ inherits                                  │
│          ┌──────────────────┼──────────────────┐                        │
│          ▼                  ▼                  ▼                        │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│  │ OrmPrimary    │  │ OrmMany2many  │  │ OrmRelations  │               │
│  │    Mixin      │  │    Mixin      │  │    Mixin      │               │
│  ├───────────────┤  ├───────────────┤  ├───────────────┤               │
│  │ • create()    │  │ • get_m2m()   │  │ • search()    │               │
│  │ • create_bulk │  │ • link_m2m()  │  │ • get_with_   │               │
│  │ • get()       │  │ • unlink_m2m()│  │   relations() │               │
│  │ • update()    │  │ • _records_   │  │ • update_with │               │
│  │ • update_bulk │  │   list_get_   │  │   _relations()│               │
│  │ • delete()    │  │   relation()  │  │               │               │
│  │ • delete_bulk │  │               │  │               │               │
│  │ • table_len() │  │               │  │               │               │
│  └───────────────┘  └───────────────┘  └───────────────┘               │
│          │                  │                  │                        │
│          └──────────────────┼──────────────────┘                        │
│                             ▼                                           │
│                    ┌───────────────┐                                    │
│                    │   DDLMixin    │                                    │
│                    ├───────────────┤                                    │
│                    │ • __create_   │                                    │
│                    │   table__()   │                                    │
│                    │ • cache()     │                                    │
│                    │ • format_     │                                    │
│                    │   default()   │                                    │
│                    └───────────────┘                                    │
│                                                                          │
│  Data Flow:                                                              │
│  ═══════════════════════════════════════════════════════════════════    │
│  User.search() → OrmRelationsMixin.search()                             │
│       │                                                                  │
│       ├─→ _builder.build_search()          # Build SQL                  │
│       ├─→ session.execute()                 # Execute query             │
│       ├─→ prepare_list_ids()                # Deserialize               │
│       └─→ _records_list_get_relation()      # Load relations            │
│                │                                                         │
│                ├─→ _builder.build_search_relation()                     │
│                ├─→ asyncio.gather(*queries)  # Parallel execution       │
│                └─→ Map results to records                               │
└─────────────────────────────────────────────────────────────────────────┘
```

### Архитектура Builder Layer

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Builder Layer                                  │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                          Builder                                  │    │
│  │                   (Main Query Builder)                           │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │ Attributes:                                              │    │    │
│  │  │  • table: str              - Target table name           │    │    │
│  │  │  • fields: dict[str,Field] - Model fields                │    │    │
│  │  │  • dialect: Dialect        - SQL dialect config          │    │    │
│  │  │  • filter_parser: Parser   - WHERE clause builder        │    │    │
│  │  └─────────────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │ inherits                                  │
│          ┌──────────────────┼──────────────────┐                        │
│          ▼                  ▼                  ▼                        │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│  │   CRUDMixin   │  │  Many2Many    │  │  Relations    │               │
│  │               │  │    Mixin      │  │    Mixin      │               │
│  ├───────────────┤  ├───────────────┤  ├───────────────┤               │
│  │build_create() │  │build_get_m2m()│  │build_search_  │               │
│  │build_create_  │  │build_get_m2m_ │  │  relation()   │               │
│  │  bulk()       │  │  multiple()   │  │               │               │
│  │build_get()    │  │               │  │ Returns:      │               │
│  │build_search() │  │               │  │ List[Request  │               │
│  │build_update() │  │               │  │   Builder]    │               │
│  │build_update_  │  │               │  │               │               │
│  │  bulk()       │  │               │  │               │               │
│  │build_delete() │  │               │  │               │               │
│  │build_delete_  │  │               │  │               │               │
│  │  bulk()       │  │               │  │               │               │
│  │build_table_   │  │               │  │               │               │
│  │  len()        │  │               │  │               │               │
│  └───────────────┘  └───────────────┘  └───────────────┘               │
│                                                                          │
│  Supporting Components:                                                  │
│  ═══════════════════════════════════════════════════════════════════    │
│                                                                          │
│  ┌───────────────────────────┐    ┌───────────────────────────┐         │
│  │       FilterParser        │    │         Dialect           │         │
│  ├───────────────────────────┤    ├───────────────────────────┤         │
│  │ • parse(filter_expr)      │    │ • name: str               │         │
│  │   → (sql, values)         │    │ • escape: str (", `)      │         │
│  │                           │    │ • placeholder: str ($, %) │         │
│  │ Supports:                 │    │ • supports_returning: bool│         │
│  │ • =, !=, >, <, >=, <=    │    │                           │         │
│  │ • like, ilike             │    │ Methods:                  │         │
│  │ • in, not in              │    │ • escape_identifier()     │         │
│  │ • is null, is not null    │    │ • make_placeholders()     │         │
│  │ • between                 │    │ • make_placeholder()      │         │
│  │ • and, or, not            │    │                           │         │
│  └───────────────────────────┘    └───────────────────────────┘         │
│                                                                          │
│  ┌───────────────────────────┐    ┌───────────────────────────┐         │
│  │     RequestBuilder        │    │   RequestBuilderForm      │         │
│  ├───────────────────────────┤    ├───────────────────────────┤         │
│  │ Container for relation    │    │ Extended for form view    │         │
│  │ query parameters          │    │ with nested fields        │         │
│  │                           │    │                           │         │
│  │ • stmt: str               │    │ Overrides:                │         │
│  │ • value: tuple            │    │ • function_prepare        │         │
│  │ • field_name: str         │    │   → prepare_form_ids      │         │
│  │ • field: Field            │    │                           │         │
│  │ • fields: list[str]       │    │                           │         │
│  │                           │    │                           │         │
│  │ Properties:               │    │                           │         │
│  │ • function_cursor         │    │                           │         │
│  │ • function_prepare        │    │                           │         │
│  └───────────────────────────┘    └───────────────────────────┘         │
│                                                                          │
│  Query Building Flow:                                                    │
│  ═══════════════════════════════════════════════════════════════════    │
│                                                                          │
│  build_search(fields, filter, limit, order, sort)                       │
│       │                                                                  │
│       ├─→ Validate fields against store_fields                          │
│       ├─→ Build SELECT clause with escaped identifiers                  │
│       ├─→ filter_parser.parse(filter) → WHERE clause                    │
│       ├─→ Add ORDER BY, LIMIT, OFFSET                                   │
│       └─→ Return (sql_string, values_tuple)                             │
│                                                                          │
│  Example Output:                                                         │
│  ───────────────────────────────────────────────────────────────────    │
│  Input:  fields=["id", "name"], filter=[("active", "=", True)]          │
│  Output: ('SELECT "id", "name" FROM users WHERE "active" = %s           │
│           ORDER BY id DESC LIMIT %s', (True, 80))                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Структура файлов

```
dotorm/
├── __init__.py              # Public API exports
├── model.py                 # DotModel base class
├── fields.py                # Field type definitions
├── exceptions.py            # Custom exceptions
├── pydantic.py              # Pydantic integration
│
├── orm/                     # ORM Layer
│   ├── __init__.py
│   ├── protocol.py          # Type protocols
│   └── mixins/
│       ├── __init__.py
│       ├── primary.py       # CRUD operations
│       ├── many2many.py     # M2M operations
│       ├── relations.py     # Relation loading
│       └── ddl.py           # Table management
│
├── builder/                 # Builder Layer
│   ├── __init__.py
│   ├── builder.py           # Main Builder class
│   ├── protocol.py          # Builder protocol
│   ├── helpers.py           # SQL helpers
│   ├── request_builder.py   # Request containers
│   └── mixins/
│       ├── __init__.py
│       ├── crud.py          # CRUD SQL builders
│       ├── m2m.py           # M2M SQL builders
│       └── relations.py     # Relation SQL builders
│
├── components/              # Shared components
│   ├── __init__.py
│   ├── dialect.py           # Database dialects
│   └── filter_parser.py     # Filter expression parser
│
└── databases/               # Database Layer
    ├── abstract/
    │   ├── __init__.py
    │   ├── pool.py          # Abstract pool
    │   ├── session.py       # Abstract session
    │   └── types.py         # Settings types
    │
    ├── postgres/
    │   ├── __init__.py
    │   ├── pool.py          # PostgreSQL pool
    │   ├── session.py       # PostgreSQL sessions
    │   └── transaction.py   # Transaction manager
    │
    ├── mysql/
    │   ├── __init__.py
    │   ├── pool.py          # MySQL pool
    │   ├── session.py       # MySQL sessions
    │   └── transaction.py   # Transaction manager
    │
    └── clickhouse/
        ├── __init__.py
        ├── pool.py          # ClickHouse pool
        └── session.py       # ClickHouse session
```

---

## 🧪 Тестирование

### Запуск тестов

```bash
# Установка зависимостей для тестирования
pip install pytest pytest-asyncio pytest-cov

# Запуск всех тестов
pytest

# С подробным выводом
pytest -v

# Только unit тесты
pytest tests/unit/ -v

# Только integration тесты (требуют БД)
pytest tests/integration/ -v

# Конкретный файл
pytest tests/unit/test_builder.py -v

# Конкретный тест
pytest tests/unit/test_builder.py::TestCRUDBuilder::test_build_search -v
```

### Покрытие тестами

```bash
# Генерация отчёта покрытия
pytest --cov=dotorm --cov-report=html

# Открыть отчёт
open htmlcov/index.html

# Текстовый отчёт в консоль
pytest --cov=dotorm --cov-report=term-missing
```

### Текущее покрытие

```
Name                                    Stmts   Miss  Cover
───────────────────────────────────────────────────────────
dotorm/__init__.py                         45      0   100%
dotorm/model.py                           285     38    87%
dotorm/fields.py                          198     12    94%
dotorm/exceptions.py                        8      0   100%
dotorm/pydantic.py                        145     23    84%
dotorm/orm/mixins/primary.py              112      8    93%
dotorm/orm/mixins/many2many.py             89     11    88%
dotorm/orm/mixins/relations.py            156     19    88%
dotorm/orm/mixins/ddl.py                   87     15    83%
dotorm/builder/builder.py                  28      0   100%
dotorm/builder/mixins/crud.py             124      5    96%
dotorm/builder/mixins/m2m.py               56      3    95%
dotorm/builder/mixins/relations.py         67      8    88%
dotorm/components/dialect.py               52      2    96%
dotorm/components/filter_parser.py         98      4    96%
dotorm/databases/postgres/session.py       89     12    87%
dotorm/databases/postgres/pool.py          67      9    87%
dotorm/databases/mysql/session.py          78     14    82%
───────────────────────────────────────────────────────────
TOTAL                                    1784    183    87%
```

### Структура тестов

```
tests/
├── conftest.py              # Pytest fixtures
├── unit/
│   ├── test_fields.py       # Field type tests
│   ├── test_model.py        # Model tests
│   ├── test_builder.py      # Builder tests
│   ├── test_filter.py       # Filter parser tests
│   └── test_dialect.py      # Dialect tests
│
├── integration/
│   ├── test_postgres.py     # PostgreSQL integration
│   ├── test_mysql.py        # MySQL integration
│   ├── test_crud.py         # CRUD operations
│   ├── test_relations.py    # Relation loading
│   └── test_transactions.py # Transaction tests
│
└── benchmarks/
    ├── test_insert.py       # Insert benchmarks
    ├── test_select.py       # Select benchmarks
    └── memory_test.py       # Memory profiling
```

### Пример теста

```python
# tests/unit/test_builder.py
import pytest
from dotorm.builder import Builder
from dotorm.components import POSTGRES
from dotorm.fields import Integer, Char, Boolean

class TestCRUDBuilder:
    @pytest.fixture
    def builder(self):
        fields = {
            "id": Integer(primary_key=True),
            "name": Char(max_length=100),
            "email": Char(max_length=255),
            "active": Boolean(default=True),
        }
        return Builder(table="users", fields=fields, dialect=POSTGRES)

    def test_build_search(self, builder):
        """Test SELECT query building."""
        stmt, values = builder.build_search(
            fields=["id", "name"],
            filter=[("active", "=", True)],
            limit=10,
            order="ASC",
            sort="name"
        )

        assert "SELECT" in stmt
        assert '"id"' in stmt
        assert '"name"' in stmt
        assert "FROM users" in stmt
        assert "WHERE" in stmt
        assert "ORDER BY name ASC" in stmt
        assert "LIMIT" in stmt
        assert values == (True, 10)

    def test_build_create(self, builder):
        """Test INSERT query building."""
        payload = {"name": "John", "email": "john@example.com"}
        stmt, values = builder.build_create(payload)

        assert "INSERT INTO users" in stmt
        assert "name" in stmt
        assert "email" in stmt
        assert "VALUES" in stmt
        assert values == ("John", "john@example.com")

    def test_build_create_bulk(self, builder):
        """Test bulk INSERT."""
        payloads = [
            {"name": "John", "email": "john@example.com"},
            {"name": "Jane", "email": "jane@example.com"},
        ]
        stmt, all_values = builder.build_create_bulk(payloads)

        assert "INSERT INTO users" in stmt
        assert "(name, email)" in stmt
        assert len(all_values) == 4
        assert all_values == ["John", "john@example.com", "Jane", "jane@example.com"]
```

---

## 📚 API Reference

### Fields

| Field | Python Type | SQL Type (PG) | Description |
|-------|-------------|---------------|-------------|
| `Integer` | `int` | `INTEGER` | 32-bit integer |
| `BigInteger` | `int` | `BIGINT` | 64-bit integer |
| `SmallInteger` | `int` | `SMALLINT` | 16-bit integer |
| `Char` | `str` | `VARCHAR(n)` | String with max length |
| `Text` | `str` | `TEXT` | Unlimited text |
| `Boolean` | `bool` | `BOOL` | True/False |
| `Float` | `float` | `DOUBLE PRECISION` | Floating point |
| `Decimal` | `Decimal` | `DECIMAL(p,s)` | Precise decimal |
| `Date` | `date` | `DATE` | Date only |
| `Time` | `time` | `TIME` | Time only |
| `Datetime` | `datetime` | `TIMESTAMPTZ` | Date and time |
| `JSONField` | `dict/list` | `JSONB` | JSON data |
| `Binary` | `bytes` | `BYTEA` | Binary data |
| `Many2one` | `Model` | `INTEGER` | FK relation |
| `One2many` | `list[Model]` | - | Reverse FK |
| `Many2many` | `list[Model]` | - | M2M relation |
| `One2one` | `Model` | - | 1:1 relation |

### Field Parameters

```python
Field(
    primary_key=False,    # Is primary key?
    null=True,            # Allow NULL?
    required=False,       # Required (sets null=False)?
    unique=False,         # Unique constraint?
    index=False,          # Create index?
    default=None,         # Default value
    description=None,     # Field description
    store=True,           # Store in DB?
    compute=None,         # Compute function
)
```

### Декораторы

| Декоратор | Когда | Зачем |
|-----------|-------|-------|
| `@onchange("field")` | На изменении поля в форме, через `/onchange` | Подставить значения в другие поля формы; только UI |
| `@depends(triggers=[...])` | После INSERT/UPDATE/DELETE, включая bulk | Хранимые вычисляемые поля (`compute=`), пересчёт родителей по связям |
| `@constrains("field")` | До INSERT/UPDATE, включая bulk | Ограничение сразу для `create`, `update`, `create_bulk`, `update_bulk` одной функцией: исключение = запрос не отправлен |

`@constrains` вызывается один раз на операцию со списком записей (`self` — пустой экземпляр модели, `records` — payload'ы), поэтому проверка батчит запросы сама. Работает из `@extend`-расширений.

### Model Class Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `create(payload)` | Create single record | `int` (ID) |
| `create_bulk(payloads)` | Create multiple records | `list[dict]` |
| `get(id, fields)` | Get by ID | `Model \| None` |
| `search(...)` | Search with filters | `list[Model]` |
| `table_len()` | Count records | `int` |
| `get_with_relations(...)` | Get with relations | `Model \| None` |
| `get_many2many(...)` | Get M2M related | `list[Model]` |
| `link_many2many(...)` | Create M2M links | `None` |
| `unlink_many2many(...)` | Remove M2M links | `None` |
| `__create_table__()` | Create DB table | `list[str]` |

### Model Instance Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `update(payload, fields)` | Update record | `None` |
| `delete()` | Delete record | `None` |
| `json(...)` | Serialize to dict | `dict` |
| `update_with_relations(...)` | Update with relations | `dict` |

---

## 👤 Автор

<p align="center">
  <img src="https://avatars.githubusercontent.com/u/11828278?v=4" width="150" style="border-radius: 50%;">
</p>

<h3 align="center">Артём Шуршилов</h3>

<p align="center">
  <a href="https://github.com/shurshilov">
    <img src="https://img.shields.io/badge/GitHub-@artem--shurshilov-181717?style=flat&logo=github" alt="GitHub">
  </a>
  <a href="https://t.me/eurodoo">
    <img src="https://img.shields.io/badge/Telegram-@artem__shurshilov-26A5E4?style=flat&logo=telegram" alt="Telegram">
  </a>
  <a href="mailto:shurshilov.a.a@gmail.com">
    <img src="https://img.shields.io/badge/Email-artem.shurshilov-EA4335?style=flat&logo=gmail" alt="Email">
  </a>
</p>

<p align="center">
  <i>Python Backend Developer | ORM Enthusiast | Open Source Contributor</i>
</p>

---

## 🤝 Контрибьютинг

Мы приветствуем вклад в развитие проекта!

```bash
# Форк репозитория, затем:
git clone https://github.com/YOUR_USERNAME/dotorm.git
cd dotorm

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или
.\venv\Scripts\activate   # Windows

# Установка зависимостей разработки
pip install -e ".[dev]"

# Создание ветки для фичи
git checkout -b feature/amazing-feature

# После изменений
pytest                    # Запуск тестов
black dotorm/             # Форматирование
mypy dotorm/              # Проверка типов

# Коммит и PR
git commit -m "feat: add amazing feature"
git push origin feature/amazing-feature
```

---

## 📄 Лицензия

```
MIT License

Copyright (c) 2024 Артём Шуршилов

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

<p align="center">
  <b>⭐ Если проект оказался полезным, поставьте звезду! ⭐</b>
</p>

<p align="center">
  Made with ❤️ by <a href="https://github.com/shurshilov">Артём Шуршилов</a>
</p>
