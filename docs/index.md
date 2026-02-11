# FARA CRM

**Внутренняя документация для разработчиков.**

FARA CRM — модульная CRM-система на FastAPI + React с кастомным ORM (DotORM), real-time чатом через WebSocket и интеграцией с внешними мессенджерами.

---

## Стек

| Слой | Технологии |
|------|-----------|
| **Backend** | Python 3.12+, FastAPI, asyncpg, PostgreSQL |
| **ORM** | DotORM (собственный async ORM) |
| **Frontend** | React 18, TypeScript, Mantine UI v8, Redux Toolkit |
| **Real-time** | WebSocket + PostgreSQL LISTEN/NOTIFY (Redis опционально) |
| **Интеграции** | Telegram, WhatsApp, Avito, Email (IMAP/SMTP) |

## Быстрый старт

=== "Backend"

    ```bash
    cd backend
    pip install -r requirements.txt
    cp .env.example .env          # настроить DB_URL
    python main.py
    ```

=== "Frontend"

    ```bash
    cd frontend
    yarn install
    yarn dev
    # http://localhost:5173
    ```

## Структура проекта

```
fara/
├── backend/
│   ├── main.py                  # FastAPI entry point
│   ├── cron_main.py             # Cron-задачи
│   ├── project_setup.py         # Models, Apps, Settings
│   └── base/
│       ├── system/              # Ядро: ORM, auth, services
│       │   ├── dotorm/          # DotORM — async ORM
│       │   ├── dotorm_crud_auto/# Авто-генерация CRUD API
│       │   ├── core/            # Environment, Service
│       │   ├── logger/
│       │   └── schemas/
│       └── crm/                 # Бизнес-модули
│           ├── chat/            # Чат + WebSocket
│           ├── security/        # ACL, сессии, роли
│           ├── users/
│           ├── leads/
│           ├── sales/
│           ├── partners/
│           ├── company/
│           ├── products/
│           ├── tasks/
│           └── ...
├── frontend/
│   └── src/
│       ├── services/api/        # RTK Query API
│       ├── store/               # Redux store
│       ├── fara_chat/           # Модуль чата
│       ├── fara_leads/
│       ├── fara_sales/
│       └── ...
├── tests/
│   ├── conftest.py
│   ├── integration/
│   └── performance/
└── docs/                        # ← эта документация
```

## Навигация

<div class="grid cards" markdown>

-   :material-server:{ .lg .middle } **Backend**

    ---

    Архитектура, DotORM, модули, API

    [:octicons-arrow-right-24: Backend](backend/index.md)

-   :material-react:{ .lg .middle } **Frontend**

    ---

    React-приложение, state management, компоненты

    [:octicons-arrow-right-24: Frontend](frontend/index.md)

-   :material-book-open:{ .lg .middle } **Гайды**

    ---

    Пошаговые инструкции: новый модуль, WebSocket, тесты

    [:octicons-arrow-right-24: Гайды](guides/index.md)

</div>
