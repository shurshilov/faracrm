# Service — базовый класс модулей

Каждый модуль в FARA CRM — это наследник `Service` или в простом случае `App`. Service управляет жизненным циклом модуля: инициализация при старте, cleanup при остановке.

## Интерфейс

```python title="backend/base/system/core/service.py"
class Service(App):
    """Базовый класс для всех модулей приложения."""

    info: dict = {}  # {"name": "...", "depends": [...]}

    async def startup(self, app: FastAPI):
        """Вызывается при запуске приложения."""
        ...

    async def shutdown(self, app: FastAPI):
        """Вызывается при остановке. Освобождает ресурсы."""
        ...

    async def post_init(self, app: FastAPI):
        """Вызывается после полной инициализации всех сервисов."""
        ...
```

## Создание сервиса

```python title="backend/base/crm/chat/app.py"
class ChatApp(Service):
    info = {
        "name": "Chat",
        "depends": ["security", "dotorm_databases_postgres"],  # (1)!
    }

    async def startup(self, app: FastAPI):
        """Запуск PubSub для real-time уведомлений."""
        await super().startup(app)

        env: Environment = app.state.env
        settings = PubSubSettings()

        backend = create_pubsub_backend(settings)
        await backend.setup(pool=env.apps.db.fara)

        chat_manager.set_pubsub(backend)
        await backend.start_listening(chat_manager.handle_pubsub_event)

    async def shutdown(self, app: FastAPI):
        """Остановка PubSub, освобождение LISTEN-соединения."""
        if chat_manager.pubsub:
            await chat_manager.pubsub.stop()    # (2)!
            chat_manager.set_pubsub(None)

    async def post_init(self, app: FastAPI):
        """Создание системных чатов при первом запуске."""
        await super().post_init(app)
        # ...создание данных по умолчанию
```

1.  Зависимости определяют порядок запуска. Chat зависит от security и DB — они будут запущены раньше.
2.  :warning: Всегда освобождайте ресурсы в `shutdown()`. PubSub listener держит соединение из пула — без cleanup пул утечёт.

## Регистрация

Сервис регистрируется в `project_setup.py` через `services_before` или `services_after`:

```python title="backend/project_setup.py"
class Apps(AppsCore):
    services_before = [
        "logger",
        "dotorm_databases_postgres",
        "security",
        "auth_token",
    ]

    services_after = [
        "dotorm_crud_auto",  # авто-CRUD после загрузки роутеров
        "chat",              # WebSocket после полной инициализации
    ]

    installed = [
        "backend.base.crm.chat",         # модуль должен иметь app.py
        "backend.base.crm.security",
        "backend.base.crm.users",
        # ...
    ]
```

!!! tip "services_before vs services_after"
    - **`services_before`** — запускаются **до** загрузки роутеров. Используй для инфраструктуры: DB, логгер, auth.
    - **`services_after`** — запускаются **после** загрузки роутеров. Используй для логики, которая зависит от роутеров (CRUD auto, WebSocket).

## Handler Errors

Сервис может регистрировать обработчики ошибок:

```python
class AuthTokenApp(Service):
    def handler_errors(self, app_server: FastAPI):
        async def catch_auth_error(request, exc):
            return JSONResponse(
                content={"error": "#FORBIDDEN"},
                status_code=401,
            )

        app_server.add_exception_handler(
            SessionNotExist, catch_auth_error
        )
```
