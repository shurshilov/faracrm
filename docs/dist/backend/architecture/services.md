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

```python title="backend/base/system/bus/app.py (сокращённо)"
class BusService(Service):
    info = {
        "name": "Bus",
        "service": True,
        "service_start_before": True,
        "sequence": 3,  # (1)!
    }

    async def startup(self, app: FastAPI):
        """LISTEN на канале шины."""
        env: Environment = app.state.env
        backend = create_pubsub_backend(env.settings.bus.backend)
        await backend.setup(pool=env.apps.db.get_pool())
        await backend.start_listening(self._dispatch)
        self._backend = backend

    async def shutdown(self, app: FastAPI):
        """Остановка LISTEN, освобождение соединения."""
        if self._backend is not None:
            await self._backend.stop()    # (2)!
            self._backend = None
```

1.  Порядок запуска — `sequence` внутри `services_before` / `services_after`. Шине нужен пул базы (`db`, sequence 2) — она стартует сразу после.
2.  :warning: Всегда освобождайте ресурсы в `shutdown()`. LISTEN держит соединение из пула — без cleanup пул утечёт.

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

## Отключаемый сервис

По умолчанию сервис — core: стартует всегда, удалить его нельзя. С `"core": False` в `info` он отключаемый — это смысл, который задаёт модуль `apps_install` (без него активно всё из `project_setup`): стартует, только если установлен (страница `/apps`), установка на ходу зовёт `startup`, удаление — `shutdown` (`AppsInstallService.sync_services`), остальные воркеры делают то же по событию `apps_changed`. Сервис, который меняет модели (студия вешает на них поля), сам пересобирает схемы и роуты авто-CRUD — `env.apps.dotorm_crud_auto.rebuild(app, env)`, если автокруд запущен (`"dotorm_crud_auto" in env.running`). Так пересборка случается только при установке и удалении на ходу: на старте процесса автокруд (sequence 10) стартует позже, при остановке — останавливается раньше. `shutdown` вызывается и при остановке процесса, поэтому он должен быть быстрым.

Флаги установки `apps_install` читает на своём старте (среди `services_before`, сразу после базы и шины), так что отключаемый сервис — в `services_after` (без `service_start_before`). Пример — студия: `"core": False, "auto_install": False, "sequence": 5` (до автокруда), в `shutdown` снимает свои поля с моделей.

## Шина событий между процессами

Воркеры и крон обмениваются событиями через системный сервис `bus` (`backend/base/system/bus`, бэкенд `bus__backend=pg|redis`). Модули друг о друге не знают: каждый подписывается на свои типы событий в своём `startup` — `env.apps.bus.subscribe(type, handler)` (`unsubscribe(type)` в `shutdown`, если сервис отключаемый) — и публикует `await env.apps.bus.publish(type, data)`. Событие получают все процессы, включая отправителя; внутри транзакции pg-бэкенд шлёт его на COMMIT. `publish` вернёт `False`, если шина не поднялась, — тогда вызывающий обрабатывает событие на месте (как сессии). Подписчики сейчас: chat (свои `PubSubCommand`), security (`session_revoked`, `session_roles_changed`), apps_install (`apps_changed`), студия (`studio_changed`).

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
