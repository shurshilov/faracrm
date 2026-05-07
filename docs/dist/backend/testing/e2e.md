# E2E тесты с Playwright

Браузерные тесты — Playwright запускает реальный Chromium (или WebKit/Firefox), кликает по UI как живой пользователь и проверяет результат. Это единственный уровень, где проверяется **что сценарий полностью работает в браузере**.

## Когда писать

- **Критические пользовательские пути**: логин, регистрация, создание основной сущности (лид, сделка), отправка сообщения.
- **Сложные интеракции**: drag-and-drop в kanban, модалки с многоступенчатыми формами, рилтайм-обновления через WebSocket.
- **Интеграции с реальным браузерным API**: WebRTC-звонки, push-уведомления, autoplay-рестрикции.

## Когда **не** писать

- Простые формы CRUD — лучше покрыть integration-тестом на API + один e2e на «логин и создать». Не нужно e2e на каждое поле формы.
- Проверки UI-стилей, отступов, цветов — это работа линтера и code review, не тестов.
- Бизнес-логика — она должна тестироваться на уровне Python, не через UI.

## Структура

```
e2e/
├── playwright.config.ts          # конфиг: браузеры, baseURL, timeouts
├── package.json
├── tests/
│   ├── auth.spec.ts              # логин, выход, восстановление пароля
│   ├── leads-crud.spec.ts        # создание/редактирование/удаление лидов
│   ├── chat.spec.ts              # отправка сообщения, real-time
│   └── calls.spec.ts             # WebRTC-звонок между двумя браузерами
└── fixtures/
    ├── users.ts                  # тестовые пользователи
    └── helpers.ts                # login(), createLead() и т.п.
```

## Пример теста

```typescript title="e2e/tests/leads-crud.spec.ts"
import { test, expect } from '@playwright/test';
import { login } from '../fixtures/helpers';

test.describe('Leads CRUD', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'manager@fara.dev', 'pass');
  });

  test('создать лида и присвоить менеджера', async ({ page }) => {
    await page.goto('/leads');
    await page.getByRole('button', { name: 'Создать' }).click();

    await page.getByLabel('Название').fill('ООО Тест');
    await page.getByLabel('Email').fill('test@example.com');
    await page.getByLabel('Менеджер').click();
    await page.getByRole('option', { name: 'Иван Иванов' }).click();
    await page.getByRole('button', { name: 'Сохранить' }).click();

    // Должны попасть на страницу созданного лида
    await expect(page).toHaveURL(/\/leads\/\d+/);
    await expect(page.getByText('ООО Тест')).toBeVisible();
  });

  test('фильтр лидов по статусу', async ({ page }) => {
    await page.goto('/leads');
    await page.getByLabel('Статус').selectOption('new');

    // Все видимые карточки имеют бейдж "Новый"
    const cards = page.getByTestId('lead-card');
    await expect(cards.first()).toBeVisible();
    for (const card of await cards.all()) {
      await expect(card.getByText('Новый')).toBeVisible();
    }
  });
});
```

## Real-time — два контекста

Для тестов чата и звонков нужно открыть **две сессии в разных браузерах**:

```typescript
test('второй пользователь видит новое сообщение', async ({ browser }) => {
  const ctx1 = await browser.newContext();
  const ctx2 = await browser.newContext();
  const page1 = await ctx1.newPage();
  const page2 = await ctx2.newPage();

  await login(page1, 'user1@fara.dev', 'pass');
  await login(page2, 'user2@fara.dev', 'pass');

  await page1.goto('/chats/17');
  await page2.goto('/chats/17');

  await page1.getByRole('textbox').fill('Привет');
  await page1.keyboard.press('Enter');

  // Второй должен увидеть сообщение через WS
  await expect(page2.getByText('Привет')).toBeVisible({ timeout: 5000 });
});
```

## Selectors

Playwright рекомендует **role-based** селекторы — они стабильнее и понятнее:

| Хорошо | Плохо |
|--------|-------|
| `page.getByRole('button', { name: 'Сохранить' })` | `page.locator('.btn-primary')` |
| `page.getByLabel('Email')` | `page.locator('#email-input')` |
| `page.getByTestId('lead-card')` | `page.locator('div.card.lead-card-item')` |

Если уж нужен testid — добавь во фронте `data-testid="lead-card"`. Он устойчив к рефакторингу класс-нейминга.

## Параллелизация

Playwright по умолчанию запускает тесты параллельно — каждый файл в своём worker. Это быстро, но требует изоляции данных:

- Создавай уникальные фикстуры в каждом тесте (`'ООО Тест ' + Date.now()`).
- Избегай хардкода ID — генерируй или ищи по уникальному имени.
- Не зависишь от порядка тестов.

Если тесты конфликтуют (например, оба меняют общий справочник) — пометь их как serial:

```typescript
test.describe.configure({ mode: 'serial' });
```

## Запуск

```bash
cd e2e

# Все тесты, headless
npx playwright test

# С UI (для отладки)
npx playwright test --ui

# Только один файл
npx playwright test leads-crud.spec.ts

# Только Chromium
npx playwright test --project=chromium

# С трейсами для отладки failed-тестов
npx playwright test --trace=on
```

## Trace viewer

Если тест упал — Playwright сохраняет trace со скриншотами на каждом шаге, network-запросами и DOM. Открыть:

```bash
npx playwright show-trace trace.zip
```

Это сильно помогает понять, где именно сломалось — особенно когда фронт зависит от анимаций или таймингов.

## CI

Playwright в Docker:

```yaml title=".github/workflows/e2e.yml"
- name: Install Playwright
  run: |
    cd e2e
    npm ci
    npx playwright install --with-deps chromium

- name: Run E2E
  run: |
    cd e2e
    npx playwright test --reporter=html
  env:
    BASE_URL: http://localhost:5173
```

В CI обычно гоняют только smoke-тесты (15-30 ключевых сценариев), потому что полный прогон может идти 30+ минут.

## См. также

- [Интеграционные тесты](integration.md) — для покрытия API без UI
- [Playwright документация](https://playwright.dev/docs/intro) — официальный гайд
