# Тестирование

## Структура тестов

```
tests/
├── conftest.py              # Fixtures: DB pool, env, client
├── integration/
│   ├── messages/
│   │   └── test_messages_api.py
│   ├── chats/
│   └── security/
└── performance/
    ├── conftest.py
    └── test_orm_performance.py
```

## Запуск

```bash
# Все тесты
pytest tests/ -v

# Только integration
pytest tests/integration/ -v -m integration

# Конкретный тест
pytest tests/integration/messages/test_messages_api.py::TestPinMessageAPI -v

# С coverage
pytest tests/ --cov=backend --cov-report=html
```

## Ключевые fixtures

### `db_pool` — asyncpg пул

Session-scoped. Создаёт пул, DDL-таблицы, устанавливает `SystemSession`:

```python
@pytest_asyncio.fixture(scope="session", autouse=True)
async def db_pool():
    pool = await asyncpg.create_pool(
        dsn=TEST_DATABASE_URL,
        min_size=5,
        max_size=10,
    )
    set_access_session(SystemSession(user_id=SYSTEM_USER_ID))
    await _create_all_tables(pool)

    yield pool

    await pool.close()
```

### `clean_all_tables` — очистка между тестами

Autouse. `TRUNCATE ... CASCADE` всех таблиц перед каждым тестом:

```python
@pytest_asyncio.fixture(autouse=True)
async def clean_all_tables(db_pool):
    tables = [m.__table__ for m in models._get_models()]
    async with db_pool.acquire() as conn:
        await conn.execute(f"TRUNCATE TABLE {', '.join(tables)} CASCADE")
```

### `app` — FastAPI приложение

```python
@pytest_asyncio.fixture
async def app(test_env):
    app = FastAPI()
    app.state.env = test_env

    await test_env.setup_services()
    await test_env.start_services_before(app)
    await test_env.load_routers(app)
    await test_env.start_services_after(app)
    test_env.add_handlers_errors(app)

    yield app

    await test_env.stop_services(app)  # (1)!
```

1. :warning: Обязательно вызывай `stop_services()` — иначе PubSub LISTEN-соединение утечёт из пула, и тесты начнут зависать.

### `authenticated_client` — HTTP-клиент с авторизацией

```python
@pytest_asyncio.fixture
async def authenticated_client(client, test_env):
    # Создаёт user + session + token
    user_id = await User.create(User(name="Test", login="test", ...))
    token = secrets.token_urlsafe(64)
    await Session.create(Session(user_id=user_id, token=token, ...))

    client.headers["Authorization"] = f"Bearer {token}"
    yield client, user_id, token
```

## Написание тестов

Подробнее: [Integration Tests](integration.md)
