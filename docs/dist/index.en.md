# FARA CRM

**Internal documentation for developers.**

FARA CRM is a modular CRM system built on FastAPI + React with a custom ORM (DotORM), real-time chat over WebSocket, and integrations with external messengers.

---

## Stack

| Layer | Technologies |
|-------|--------------|
| **Backend** | Python 3.12+, FastAPI, asyncpg, PostgreSQL |
| **ORM** | DotORM (custom async ORM) |
| **Frontend** | React 18, TypeScript, Mantine UI v8, Redux Toolkit |
| **Real-time** | WebSocket + PostgreSQL LISTEN/NOTIFY (Redis optional) |
| **Integrations** | Telegram, WhatsApp, Avito, Email (IMAP/SMTP) |

## Quick start

=== "Backend"

    ```bash
    pip install -r requirements.txt
    cp .env.example .env # setup your credentials
    uvicorn backend.main:app --host 0.0.0.0 --port 8090 # or click f5 (vs code)
    ```

=== "Frontend"

    ```bash
    cd frontend
    yarn install
    yarn dev
    # http://127.0.0.1:5173
    ```

## Project structure

```
fara/
├── backend/
│   ├── main.py                  # FastAPI entry point
│   ├── main_cron.py             # Cron jobs
│   ├── project_setup.py         # Models, Apps, Settings
│   └── base/
│       ├── system/              # Core: ORM, auth, services
│       │   ├── dotorm/          # DotORM — async ORM
│       │   ├── dotorm_crud_auto/# Auto-generated CRUD API
│       │   ├── core/            # Environment, Service
│       │   ├── logger/
│       │   └── schemas/
│       └── crm/                 # Business modules
│           ├── chat/            # Chat + WebSocket
│           ├── security/        # ACL, sessions, roles
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
│       ├── fara_chat/           # Chat module
│       ├── fara_leads/
│       ├── fara_sales/
│       └── ...
├── tests/
│   ├── conftest.py
│   ├── integration/
│   └── performance/
└── docs/                        # ← this documentation
```

## Navigation

<div class="grid cards" markdown>

-   :material-server:{ .lg .middle } **Backend**

    ---

    Architecture, DotORM, modules, API

    [:octicons-arrow-right-24: Backend](backend/index.md)

-   :material-react:{ .lg .middle } **Frontend**

    ---

    React app, state management, components

    [:octicons-arrow-right-24: Frontend](frontend/index.md)

-   :material-book-open:{ .lg .middle } **Guides**

    ---

    Step-by-step: new module, WebSocket, tests

    [:octicons-arrow-right-24: Guides](guides/index.md)

</div>
