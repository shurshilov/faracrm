# FARA CRM — E2E тесты (Playwright)

## Установка

```bash
cd tests/e2e
npm install
npx playwright install chromium
```

## Запуск

```bash
# Всё
npm test

# Только чаты и WebSocket (основное покрытие)
npm run test:chat

# Только WebSocket (Node.js клиент, без браузера)
npm run test:ws

# Multi-tab тесты (2 браузера одновременно)
npm run test:multitab

# С визуальным браузером
npm run test:headed

# Интерактивный UI для дебага
npm run test:ui

# Debug mode (step-by-step)
npm run test:debug

# Отчёт после прогона
npm run report
```

## Требования

- Запущенный бэкенд: `http://localhost:8090`
- Запущенный фронтенд: `http://localhost:5173`
- Пользователь `admin` / `admin`

Переменные окружения:
```bash
BASE_URL=http://localhost:5173
API_URL=http://localhost:8090
```

## Структура

```
e2e/
├── playwright.config.ts     # Конфигурация
├── package.json             # Зависимости
├── fixtures/
│   ├── global-setup.ts      # Логин + создание тестовых юзеров
│   └── index.ts             # Расширенные fixtures (api, ws, user2Page)
├── helpers/
│   ├── api.helper.ts        # HTTP вызовы для setup/teardown
│   └── ws.helper.ts         # Node.js WebSocket клиент
├── pages/
│   ├── LoginPage.ts         # Page Object: авторизация
│   ├── ChatPage.ts          # Page Object: чат
│   └── ListPage.ts          # Page Object: List/Kanban/Gantt
└── specs/
    ├── auth/
    │   └── login.spec.ts          # 4 теста: логин, ошибки
    ├── chat/
    │   ├── chat-messaging.spec.ts # 5 тестов: UI отправка/edit/delete
    │   ├── chat-websocket.spec.ts # 15 тестов: WS события между юзерами
    │   ├── chat-multitab.spec.ts  # 6 тестов: 2 браузера real-time
    │   └── chat-edge-cases.spec.ts# 8 тестов: reconnect, burst, isolation
    ├── crud/
    │   └── search.spec.ts         # 3 теста: поиск в List/Kanban
    └── views/
        └── theme-switch.spec.ts   # 1 тест: переключение темы
```

## Покрытие WebSocket событий

| Событие | Тест |
|---------|------|
| `ping/pong` | chat-websocket: heartbeat |
| `subscribe/subscribed` | chat-websocket: подписка |
| `subscribe_all` | chat-websocket: массовая подписка |
| `unsubscribe` | chat-edge-cases: отписка |
| `new_message` | chat-websocket: 4 теста (отправка, порядок, exclude) |
| `message_edited` | chat-websocket: редактирование |
| `message_deleted` | chat-websocket: удаление |
| `typing` | chat-websocket: индикатор набора |
| `messages_read` | chat-websocket: отметка прочтения |
| `presence` | chat-websocket: online/offline |
| `chat_created` | chat-websocket: создание чата |
| UI sync | chat-multitab: все операции через 2 браузера |
| reconnect | chat-edge-cases: переподключение |
| duplicate conn | chat-edge-cases: дублирование |
| auth errors | chat-edge-cases: невалидный/отсутствующий токен |
| isolation | chat-edge-cases: изоляция подписок |
| burst | chat-edge-cases: 10 сообщений без пауз |
| 50 chats | chat-edge-cases: массовая подписка |

## Архитектурные решения

**Почему Playwright, не Cypress:** multi-tab (2 браузера для чат-тестов), native async/await, Node.js WS клиент работает в тестовом процессе а не в браузере.

**Почему API для setup:** создание чатов/сообщений через UI медленно и хрупко. API helpers создают данные за миллисекунды, тесты проверяют только UI/WS поведение.

**Fixtures вместо beforeAll:** Playwright fixtures — dependency injection с автоматическим cleanup. `adminWS` fixture создаёт WebSocket, после теста автоматически закрывает.

**Page Objects:** локаторы вынесены в классы, тесты читаются как бизнес-сценарии.
