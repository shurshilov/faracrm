# Архитектура Backend

## Обзор

```mermaid
graph TB
    subgraph FastAPI["FastAPI Application"]
        MW[Middleware: Auth, CORS]
        R[Routers]
    end

    subgraph Environment
        S[Settings]
        M[Models]
        A[Apps / Services]
    end

    subgraph Services
        DB[PostgresDB Service]
        AUTH[AuthToken Service]
        CHAT[Chat Service]
        CRUD[CRUD Auto Service]
        SEC[Security Service]
    end

    subgraph DotORM
        MOD[DotModel]
        BLD[Builder]
        SES[Session / Pool]
    end

    FastAPI --> Environment
    Environment --> Services
    Services --> DotORM
    DotORM --> PG[(PostgreSQL)]
    CHAT --> WS[WebSocket Manager]
    WS --> PUBSUB[PubSub: PG LISTEN/NOTIFY]
    PUBSUB --> PG
```

## Жизненный цикл приложения

Приложение запускается в определённом порядке — это критично для корректной инициализации:

```mermaid
sequenceDiagram
    participant M as main.py
    participant E as Environment
    participant SB as services_before
    participant SA as services_after

    M->>E: Environment(Settings, Models, Apps)
    E->>E: setup_services()
    E->>SB: start_services_before(app)
    Note over SB: DB Pool, Logger, Security
    E->>E: load_routers(app)
    E->>SA: start_services_after(app)
    Note over SA: CRUD Auto, Chat PubSub
    E->>E: start_post_init(app)
    Note over E: Default data, migrations
```

### Порядок запуска сервисов

```python title="backend/project_setup.py"
class Apps(AppsCore):
    """Определяет порядок инициализации модулей."""

    services_before = [
        "logger",                     # 1. Логирование
        "dotorm_databases_postgres",   # 2. DB Pool
        "security",                    # 3. ACL, роли
        "auth_token",                  # 4. Аутентификация
    ]

    services_after = [
        "dotorm_crud_auto",           # 5. CRUD роутеры
        "chat",                       # 6. WebSocket + PubSub
    ]
```

!!! warning "Порядок важен"
    `services_before` запускаются **до** загрузки роутеров — они настраивают DB pool, без которого роутеры не могут работать. `services_after` запускаются **после** — они могут использовать роутеры и другие сервисы.

## Модульная структура

Каждый CRM-модуль — это папка с фиксированной структурой:

```
backend/base/crm/chat/
├── app.py              # Service: startup/shutdown
├── models/             # DotModel-классы
│   ├── chat.py
│   ├── chat_message.py
│   └── chat_member.py
├── routers/            # FastAPI роутеры
│   ├── chats.py
│   └── messages.py
├── schemas/            # Pydantic-схемы (если нужны)
└── websocket/          # Доп. логика (WS, pubsub)
```

Регистрация модуля в `project_setup.py`:

```python title="backend/project_setup.py"
class Models(ModelsCore):
    # Каждая модель получает CRUD API автоматически
    chat = Chat
    chat_message = ChatMessage
    chat_member = ChatMember
    user = User
    # ...
```

## Request Lifecycle

```mermaid
sequenceDiagram
    participant C as Client
    participant MW as Auth Middleware
    participant R as Router
    participant ORM as DotORM
    participant DB as PostgreSQL

    C->>MW: POST /chats/1/messages
    MW->>MW: verify_access(token)
    MW->>MW: set_access_session(session)
    MW->>R: pin_message(req, chat_id, msg_id)
    R->>ORM: ChatMember.check_can_pin(...)
    ORM->>DB: SELECT ... FROM chat_members
    DB-->>ORM: row
    R->>ORM: message.update(pinned=True)
    ORM->>DB: UPDATE chat_messages SET pinned=true
    R->>R: chat_manager.send_to_chat(ws_event)
    R-->>C: {"success": true}
```
