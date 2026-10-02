<div align="center">
  <img src="docs/dist/assets/logo-mark.svg" alt="FARA CRM" width="96" height="96" />

  [English](README.md) · [Русский](README.ru.md)
</div>

# FARA CRM

**Modular CRM system built on FastAPI + React with a custom ORM (DotORM), real-time chat via WebSocket, and integrations with external messengers.**

🌐 **Official site:** [faracrm.com](https://faracrm.com)
🕹️ **Demo:** [demo.faracrm.com](https://demo.faracrm.com)
📖 **Full documentation:** [docs.faracrm.com](https://docs.faracrm.com)

---

## Stack

| Layer | Technologies |
|------|-----------|
| **Backend** | Python 3.12+, FastAPI, asyncpg, PostgreSQL |
| **ORM** | DotORM (in-house async ORM) |
| **Frontend** | React 19, TypeScript, Mantine UI v8, Redux Toolkit |
| **Real-time** | WebSocket + PostgreSQL LISTEN/NOTIFY (redis optional) |
| **Integrations** | Telegram, WhatsApp, Avito, VK, Maks Email (IMAP/SMTP) |
| **Telephony** | Asterisk, Sipuni, Megafon, Mts, Beeline |

## Quick start

### Docker
<small>It is used for running locally without dependencies and for demonstrating capabilities; there is also a production build, but that is a separate script.</small>

```bash
docker compose -f docker-compose.dev.yml up --build
```

- Frontend: http://127.0.0.1:7777
- Backend API: http://127.0.0.1:7777/api/
- Backend direct: http://127.0.0.1:8000

### Local development
<small>Used by developers for modifications; includes debug mode and other useful IDE features.</small>

**Backend:**
```bash
# F5 if you use VS Code
# or:
pip install -r requirements.txt
cp .env.sample .env
uvicorn backend.main:app --host 0.0.0.0 --port 8090
```

**Frontend:**
```bash
cd frontend
yarn install
yarn dev
```
### Production
<small>Check the documentation, specifically the deployment guide section.</small>


## Project layout

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
│       │   └── schemas/
│       └── crm/                 # Business modules
│           ├── chat/            # Chat + WebSocket
│           ├── security/        # ACL, sessions, roles
│           ├── users/
│           ├── leads/
│           ├── sales/
│           ├── partners/
│           ├── tasks/
│           └── ...
├── frontend/
│   └── src/
│       ├── services/api/        # RTK Query API
│       ├── store/               # Redux store
│       ├── fara_chat/           # Chat module
│       └── ...
├── tests/
├── docs/                        # MkDocs documentation
└── docker-compose.yml
```

## Documentation

The documentation lives in `docs/` and is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

| Section | Description |
|--------|----------|
| [Backend](docs/backend/index.md) | Architecture, DotORM, modules, API |
| [Frontend](docs/frontend/index.md) | React app, state management |
| [Guides](docs/guides/index.md) | New module, WebSocket, tests |

## Demo

🌐 [demo.faracrm.com](https://demo.faracrm.com)

## License

FARA CRM License v1.0
