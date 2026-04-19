import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright конфигурация для FARA CRM E2E тестов.
 *
 * Запуск:
 *   npx playwright test                        — все тесты КРОМЕ smoke
 *                                                (по умолчанию, включая
 *                                                 complex-create, theme и т.д.)
 *   npx playwright test --project=smoke        — только smoke-тесты
 *   npx playwright test specs/chat/            — конкретная папка
 *   npx playwright test --headed               — с браузером
 *   npx playwright test --ui                   — интерактивный режим
 */

const BASE_URL = process.env.BASE_URL || "http://127.0.0.1:5173";
const API_URL = process.env.API_URL || "http://127.0.0.1:8090";

export default defineConfig({
  testDir: "./specs",

  /* Таймауты */
  timeout: 30_000,
  expect: { timeout: 10_000 },

  /* Параллельный запуск — ограничен из-за WS (1 соединение на user) */
  fullyParallel: false,
  workers: process.env.CI ? 1 : 4,

  /* Репортеры */
  reporter: process.env.CI
    ? [["html", { open: "never" }], ["github"]]
    : [["html", { open: "on-failure" }]],

  /* Retry при падениях */
  retries: process.env.CI ? 2 : 0,

  /* Глобальный setup — авторизация */
  globalSetup: "./fixtures/global-setup.ts",

  use: {
    baseURL: BASE_URL,
    /* Trace для дебага упавших тестов */
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "on-first-retry",
    /* Локаль */
    locale: "ru-RU",
    /* Авторизованное состояние по умолчанию */
    storageState: ".auth/admin.json",
  },

  /* Проекты:
   * - chromium (default) — все тесты кроме smoke. Запускается без флагов.
   * - smoke — только smoke-тесты. Запуск: --project=smoke.
   *
   * Логика: smoke прогоняет открытие ~60 страниц и занимает много времени,
   * его нужно запускать осознанно (перед релизом, в ночных job'ах CI),
   * а обычная разработка использует быстрый complex-create + views + auth.
   */
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      testIgnore: /specs\/smoke\//,
    },
    {
      name: "smoke",
      use: { ...devices["Desktop Chrome"] },
      testMatch: /specs\/smoke\//,
    },
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
  ],
});
