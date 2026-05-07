# Backend

FastAPI application with a modular architecture, custom ORM, and auto-generated CRUD API.

## Key concepts

**Environment** — the central application object. Contains `models`, `apps`, `settings` and manages service lifecycle.

**Service** — base class for modules. Each module (chat, security, users...) is a `Service` with `startup()`, `shutdown()`, `post_init()` methods.

**DotORM** — async ORM with declarative models, auto-generated DDL, and CRUD API.

## Entry Points

```python title="backend/main.py"
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifecycle — start and stop services."""
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

## Sections

| Section | Description |
|---------|-------------|
| [Architecture](architecture/overview.md) | Environment, Service, lifecycle |
| [DotORM](dotorm/index.md) | Models, fields, queries, relations |
| [Modules](modules/chat.md) | Chat, Security, and other CRM modules |
| [Testing](testing/index.md) | pytest, fixtures, integration tests |
