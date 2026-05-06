# Frontend

React SPA на TypeScript с Mantine UI, Redux Toolkit и модульной архитектурой.

## Стек

| Технология | Версия | Назначение |
|-----------|--------|-----------|
| React | 18 | UI framework |
| TypeScript | 5 | Типизация |
| Mantine | 8 | UI-компоненты |
| Redux Toolkit | — | State management |
| RTK Query | — | Data fetching + кэширование |
| Vite | — | Сборка |
| i18next | — | Интернационализация (ru/en) |

## Запуск

```bash
cd frontend
yarn install
yarn dev
# or npm
# npm install
# npm run dev       # http://localhost:5173
# npm run build     # production build
# npm run lint      # ESLint
```

## Структура

```
frontend/src/
├── main.tsx                # Entry point
├── App.tsx                 # Root component + providers
├── config/                 # API URL, env config
├── store/                  # Redux store
├── slices/                 # Redux slices (auth, etc.)
├── services/
│   ├── api/                # RTK Query endpoints
│   │   ├── crudApi.ts      # Универсальный CRUD API
│   │   ├── chat.ts
│   │   └── users.ts
│   ├── auth/               # Auth service
│   └── hooks/              # Custom hooks
├── route/                  # Routing
├── layout/                 # App layout
├── locales/                # i18n translations
│   ├── ru/
│   └── en/
├── shared/                 # Shared utilities
├── types/                  # Global TypeScript types
├── assets/                 # Images, icons
│
├── fara_chat/              # Модуль чата
├── fara_leads/             # Модуль лидов
├── fara_sales/             # Модуль продаж
├── fara_partners/          # Модуль партнёров
├── fara_products/          # Модуль товаров
├── fara_tasks/             # Модуль задач
├── fara_users/             # Модуль пользователей
├── fara_security/          # Модуль безопасности
├── fara_company/           # Модуль компаний
└── fara_contract/          # Модуль договоров
```

## Разделы

- [Архитектура](architecture/overview.md) — компоненты, модули, routing
- [State Management](architecture/state.md) — Redux store, RTK Query
- [Модули](modules/chat.md) — Chat UI
- [API-сервисы](services/crud-api.md) — CRUD API клиент
