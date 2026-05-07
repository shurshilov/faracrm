# Frontend

React SPA in TypeScript with Mantine UI, Redux Toolkit, and a modular architecture.

## Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 18 | UI framework |
| TypeScript | 5 | Type safety |
| Mantine | 8 | UI components |
| Redux Toolkit | — | State management |
| RTK Query | — | Data fetching + caching |
| Vite | — | Build tool |
| i18next | — | Internationalization (ru/en) |

## Running

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

## Structure

```
frontend/src/
├── main.tsx                # Entry point
├── App.tsx                 # Root component + providers
├── config/                 # API URL, env config
├── store/                  # Redux store
├── slices/                 # Redux slices (auth, etc.)
├── services/
│   ├── api/                # RTK Query endpoints
│   │   ├── crudApi.ts      # Universal CRUD API
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
├── fara_chat/              # Chat module
├── fara_leads/             # Leads module
├── fara_sales/             # Sales module
├── fara_partners/          # Partners module
├── fara_products/          # Products module
├── fara_tasks/             # Tasks module
├── fara_users/             # Users module
├── fara_security/          # Security module
├── fara_company/           # Companies module
└── fara_contract/          # Contracts module
```

## Sections

- [Architecture](architecture/overview.md) — components, modules, routing
- [State Management](architecture/state.md) — Redux store, RTK Query
- [Modules](modules/chat.md) — Chat UI
- [API services](services/crud-api.md) — CRUD API client
