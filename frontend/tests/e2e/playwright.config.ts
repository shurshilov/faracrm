import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright конфигурация для FARA CRM E2E тестов.
 *
 * Запуск:
 *   npx playwright test                      — все тесты
 *   npx playwright test specs/chat/           — только чат
 *   npx playwright test --headed              — с браузером
 *   npx playwright test --ui                  — интерактивный режим
 */

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const API_URL = process.env.API_URL || 'http://localhost:8090';

export default defineConfig({
  testDir: './specs',

  /* Таймауты */
  timeout: 30_000,
  expect: { timeout: 10_000 },

  /* Параллельный запуск */
  fullyParallel: true,
  workers: process.env.CI ? 1 : undefined,

  /* Репортеры */
  reporter: process.env.CI
    ? [['html', { open: 'never' }], ['github']]
    : [['html', { open: 'on-failure' }]],

  /* Retry при падениях */
  retries: process.env.CI ? 2 : 0,

  /* Глобальный setup — авторизация */
  globalSetup: './fixtures/global-setup.ts',

  use: {
    baseURL: BASE_URL,
    /* Trace для дебага упавших тестов */
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
    /* Локаль */
    locale: 'ru-RU',
    /* Авторизованное состояние по умолчанию */
    storageState: '.auth/admin.json',
  },

  /* Проекты = браузеры */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
  ],
});
