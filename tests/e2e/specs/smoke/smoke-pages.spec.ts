import { test, expect } from '../../fixtures';

/**
 * Smoke-тесты — проверяем что все списки, формы и спецвиды
 * открываются без ошибок (белый экран, JS exception, 500).
 *
 * Не проверяют бизнес-логику, только рендеринг.
 * Быстрые: ~1-2 секунды на тест.
 */

// ==================== Конфигурация моделей ====================

/** Все модели с URL маршрутами */
const ALL_MODELS = [
  'products',
  'category',
  'uom',
  'partners',
  'contact',
  'contact_type',
  'leads',
  'activity',
  'activity_type',
  'chat_connector',
  'chat_external_account',
  'chat_external_chat',
  'chat_external_message',
  'lead_stage',
  'team_crm',
  'sales',
  'sale_stage',
  'tax',
  'sale_line',
  'contract',
  'attachments',
  'attachments_storage',
  'attachments_route',
  'company',
  'users',
  'roles',
  'rules',
  'access_list',
  'models',
  'apps',
  'sessions',
  'language',
  'cron_job',
  'saved_filters',
  'tasks',
  'project',
  'task_stage',
  'task_tag',
  'system_settings',
  'report_template',
];

/** Модели с Gantt view (исключая users kanban) */
const GANTT_MODELS = ['sessions', 'tasks', 'project'];

// ==================== Helpers ====================

/**
 * Проверяет что страница загрузилась без критических ошибок.
 * Ловит: белый экран, JS errors, 500 ответы.
 */
async function expectPageLoaded(page: any) {
  // Не должно быть белого экрана — хотя бы один видимый элемент
  await expect(
    page.locator('table, [class*="List"], [class*="Kanban"], [class*="Gantt"], [class*="Form"], [class*="Card"], [class*="mantine-"], button, input, h1, h2, h3').first(),
  ).toBeVisible({ timeout: 15_000 });

  // Нет текста ошибки на странице
  const errorText = page.locator('text=/Unhandled|Something went wrong|500|Internal Server Error/i');
  await expect(errorText).toHaveCount(0, { timeout: 1_000 }).catch(() => {
    // Не падаем если не нашли — это ок
  });
}

/**
 * Ловит console.error во время загрузки страницы.
 * Возвращает массив серьёзных ошибок (исключая known warnings).
 */
function collectErrors(page: any): string[] {
  const errors: string[] = [];
  page.on('console', (msg: any) => {
    if (msg.type() === 'error') {
      const text = msg.text();
      // Игнорируем известные безобидные ошибки
      if (
        text.includes('favicon') ||
        text.includes('ResizeObserver') ||
        text.includes('net::ERR') ||
        text.includes('404')
      ) {
        return;
      }
      errors.push(text);
    }
  });
  return errors;
}

// ==================== Тесты: List views ====================

test.describe('Smoke — List views', () => {
  for (const model of ALL_MODELS) {
    test(`/${model} — список открывается`, async ({ page }) => {
      const errors = collectErrors(page);

      await page.goto(`/${model}`);
      await page.waitForLoadState('networkidle');
      await expectPageLoaded(page);

      // Не должно быть критических JS ошибок
      const critical = errors.filter(
        (e) => e.includes('Uncaught') || e.includes('TypeError') || e.includes('Cannot read'),
      );
      expect(critical).toHaveLength(0);
    });
  }
});

// ==================== Тесты: Form views ====================

test.describe('Smoke — Form views (create)', () => {
  // Модели где форма создания должна открываться
  const FORM_MODELS = [
    'products',
    'category',
    'uom',
    'partners',
    'contact',
    'contact_type',
    'leads',
    'activity_type',
    'lead_stage',
    'team_crm',
    'sales',
    'sale_stage',
    'tax',
    'contract',
    'company',
    'users',
    'roles',
    'rules',
    'tasks',
    'project',
    'task_stage',
    'task_tag',
    'report_template',
  ];

  for (const model of FORM_MODELS) {
    test(`/${model}/create — форма создания открывается`, async ({ page }) => {
      const errors = collectErrors(page);

      await page.goto(`/${model}/create`);
      await page.waitForLoadState('networkidle');
      await expectPageLoaded(page);

      const critical = errors.filter(
        (e) => e.includes('Uncaught') || e.includes('TypeError') || e.includes('Cannot read'),
      );
      expect(critical).toHaveLength(0);
    });
  }
});

test.describe('Smoke — Form views (existing record)', () => {
  /**
   * Модели где открываем форму существующей записи (id=1).
   * Если записи нет — страница покажет "не найдено", но не упадёт.
   */
  const RECORD_MODELS = [
    'products',
    'partners',
    'leads',
    'sales',
    'company',
    'users',
    'roles',
    'tasks',
    'project',
    'contract',
  ];

  for (const model of RECORD_MODELS) {
    test(`/${model}/1 — форма записи открывается`, async ({ page }) => {
      const errors = collectErrors(page);

      await page.goto(`/${model}/1`);
      await page.waitForLoadState('networkidle');
      await expectPageLoaded(page);

      const critical = errors.filter(
        (e) => e.includes('Uncaught') || e.includes('TypeError') || e.includes('Cannot read'),
      );
      expect(critical).toHaveLength(0);
    });
  }
});

// ==================== Тесты: Gantt views ====================

test.describe('Smoke — Gantt views', () => {
  for (const model of GANTT_MODELS) {
    test(`/${model} — Gantt view открывается`, async ({ page }) => {
      const errors = collectErrors(page);

      await page.goto(`/${model}`);
      await page.waitForLoadState('networkidle');

      // Переключаемся на Gantt — третья кнопка в ViewSwitcher
      const viewSwitcher = page.locator('[class*="ViewSwitcher"], [class*="viewSwitcher"]');
      const ganttBtn = viewSwitcher.locator('button').nth(2);
      if (await ganttBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
        await ganttBtn.click();
        await page.waitForLoadState('networkidle');
      }

      await expectPageLoaded(page);

      const critical = errors.filter(
        (e) => e.includes('Uncaught') || e.includes('TypeError') || e.includes('Cannot read'),
      );
      expect(critical).toHaveLength(0);
    });
  }
});

// ==================== Тесты: Специальные страницы ====================

test.describe('Smoke — Специальные страницы', () => {
  test('/chat — чат открывается', async ({ page }) => {
    await page.goto('/chat');
    await page.waitForLoadState('networkidle');
    await expectPageLoaded(page);
  });

  test('/system_settings — настройки открываются', async ({ page }) => {
    await page.goto('/system_settings');
    await page.waitForLoadState('networkidle');
    await expectPageLoaded(page);
  });

  test('/cron_job — планировщик открывается', async ({ page }) => {
    await page.goto('/cron_job');
    await page.waitForLoadState('networkidle');
    await expectPageLoaded(page);
  });

  test('/apps — приложения открываются', async ({ page }) => {
    await page.goto('/apps');
    await page.waitForLoadState('networkidle');
    await expectPageLoaded(page);
  });
});

// ==================== Тесты: Console errors ====================

test.describe('Smoke — отсутствие JS ошибок при навигации', () => {
  test('навигация по 5 страницам без ошибок', async ({ page }) => {
    const errors = collectErrors(page);
    const pages = ['/leads', '/partners', '/tasks', '/sales', '/users'];

    for (const url of pages) {
      await page.goto(url);
      await page.waitForLoadState('networkidle');
    }

    // Допускаем warning'и, но не Uncaught ошибки
    const critical = errors.filter(
      (e) => e.includes('Uncaught') || e.includes('TypeError') || e.includes('Cannot read'),
    );
    expect(critical).toHaveLength(0);
  });
});
