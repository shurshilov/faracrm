# FARA CRM

**Модульная CRM-система на FastAPI + React с кастомным ORM (DotORM), real-time чатом через WebSocket и интеграцией с внешними мессенджерами.**

**Официальный сайт:** [faracrm.com](https://faracrm.com)
**Демо версия:** [demo.faracrm.com](https://demo.faracrm.com)
📖 **Полная документация:** [docs.faracrm.com](https://docs.faracrm.com)

---

## Стек

| Слой | Технологии |
|------|-----------|
| **Backend** | Python 3.12+, FastAPI, asyncpg, PostgreSQL |
| **ORM** | DotORM (собственный async ORM) |
| **Frontend** | React 18, TypeScript, Mantine UI v8, Redux Toolkit |
| **Real-time** | WebSocket + PostgreSQL LISTEN/NOTIFY |
| **Интеграции** | Telegram, WhatsApp, Avito, Email (IMAP/SMTP) |

## Быстрый старт

### Docker (рекомендуется)

```bash
docker compose up --build
```

- Frontend: http://localhost:7777
- Backend API: http://localhost:7777/api/
- Backend direct: http://localhost:8000

### Локально для разработки

**Backend:**
```bash
# F5 если используете VS code
# или:
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --host 0.0.0.0 --port 8090
```

**Frontend:**
```bash
cd frontend
yarn install
yarn dev
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
│       │   └── schemas/
│       └── crm/                 # Бизнес-модули
│           ├── chat/            # Чат + WebSocket
│           ├── security/        # ACL, сессии, роли
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
│       ├── fara_chat/           # Модуль чата
│       └── ...
├── tests/
├── docs/                        # MkDocs документация
└── docker-compose.yml
```

## Документация

Документация написана в `docs/` и собирается через [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

| Раздел | Описание |
|--------|----------|
| [Backend](docs/backend/index.md) | Архитектура, DotORM, модули, API |
| [Frontend](docs/frontend/index.md) | React-приложение, state management |
| [Гайды](docs/guides/index.md) | Новый модуль, WebSocket, тесты |

## Демо

🌐 [demo.faracrm.com](https://demo.faracrm.com)

## Лицензия

FARA CRM License v1.0