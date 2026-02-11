# Backend

FastAPI-приложение с модульной архитектурой, кастомным ORM и автогенерацией CRUD API.

## Ключевые концепции

**Environment** — центральный объект приложения. Содержит `models`, `apps`, `settings` и управляет жизненным циклом сервисов.

**Service** — базовый класс модулей. Каждый модуль (chat, security, users...) — это `Service` с методами `startup()`, `shutdown()`, `post_init()`.

**DotORM** — асинхронный ORM с декларативными моделями, автогенерацией DDL и CRUD API.

## Entry Points

```python title="backend/main.py"
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifecycle — запуск и остановка сервисов."""
    env = Environment(Settings, Models, Apps)
    application.state.env = env

    await env.setup_services()
    await env.start_services_before(application)
    await env.load_routers(application)
    await env.start_services_after(application)
    await env.start_post_init(application)

    yield

    await env.stop_services(application)

app = FastAPI(lifespan=lifespan)
```

## Разделы

| Раздел | Описание |
|--------|----------|
| [Архитектура](architecture/overview.md) | Environment, Service, жизненный цикл |
| [DotORM](dotorm/index.md) | Модели, поля, запросы, связи |
| [Модули](modules/chat.md) | Чат, Security и другие CRM-модули |
| [Тестирование](testing/index.md) | pytest, fixtures, integration tests |
