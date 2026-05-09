import { test, expect, Page } from '../../fixtures';

/**
 * E2E: создание пользователя через UI (/users → "Создать" → форма).
 *
 * Форма пользователя (frontend/src/fara_users/Form.tsx) на этапе создания
 * требует только два поля: `name` и `login`. Остальное имеет default'ы:
 *   - lang_id: backend default = 'en' (см. _default_lang)
 *   - is_admin: false (Boolean default)
 *   - role_ids: backend default = base_user (_default_roles)
 * Пароль на этапе создания НЕ задаётся — для этого есть отдельная модалка
 * ChangePasswordModal, доступная только для уже существующего пользователя.
 *
 * Селекторы и хелперы взяты из crud/complex-create.spec.ts. Намеренно
 * локальные копии, чтобы файл был самодостаточным и не плодил импорт-цепочки
 * с другим спеком; если в будущем хелперов станет много — стоит вынести в
 * tests/e2e/helpers/form.helper.ts.
 */

// ==================== Helpers ====================

async function clickCreate(page: Page) {
  const createBtn = page
    .getByRole('button', { name: /^(создать|create|добавить|\+)$/i })
    .first();
  await createBtn.waitFor({ state: 'visible', timeout: 10_000 });
  await createBtn.click();
  await page
    .waitForURL(/\/create$|\/[^/]+\/create/, { timeout: 5_000 })
    .catch(() => {});
  await page
    .locator('[data-path]')
    .first()
    .waitFor({ state: 'attached', timeout: 5_000 });
}

/**
 * Кликает по кнопке сохранения формы (Toolbar), пропуская кнопки
 * внутри O2M-виджетов и диалогов. Логика та же что в complex-create.spec.ts.
 */
async function clickSave(page: Page) {
  const btn = await page.evaluateHandle(() => {
    const texts = /^(сохранить|save|saving|создать|create|добавить|add)$/i;
    const allButtons = Array.from(document.querySelectorAll('button'));
    const candidates = allButtons.filter(b => {
      const text = (b.textContent || '').trim();
      if (!texts.test(text)) return false;
      const rect = b.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return false;
      if (b.closest('table, [class*="DataTable"], [class*="fieldRelation"]'))
        return false;
      if (b.closest('[role="dialog"]')) return false;
      return true;
    });
    return candidates[0] || null;
  });

  const element = btn.asElement();
  if (!element) {
    throw new Error('clickSave: не найдена кнопка сохранения формы (Toolbar)');
  }
  await element.scrollIntoViewIfNeeded();
  await element.click();
  await page.waitForTimeout(300);
}

async function fillByName(page: Page, name: string, value: string) {
  const input = page.locator(`[data-path="${name}"]`).first();
  await input.waitFor({ state: 'visible', timeout: 10_000 });
  await input.fill(value);
}

/**
 * Дамп ошибок валидации формы — копия отладочного блока из complex-create.spec.
 * Вызывается, когда после save URL остался на /create.
 */
async function dumpFormState(page: Page, label: string) {
  const errors = await page
    .locator('.mantine-TextInput-error, [class*="error"], [data-error="true"]')
    .allTextContents();
  const values = await page.evaluate(() => {
    const inputs = document.querySelectorAll('[data-path]');
    return Array.from(inputs).map(el => ({
      path: el.getAttribute('data-path'),
      value: (el as HTMLInputElement).value,
    }));
  });
  console.log(`[${label}] form still on /create. Field errors:`, errors);
  console.log(`[${label}] field values:`, JSON.stringify(values, null, 2));
}

// ==================== Tests ====================

test.describe('test_create_user', () => {
  test.describe.configure({ mode: 'serial' });

  // Список созданных id для очистки. Запоминаем именно login — id получаем
  // в afterAll через api.searchRecords (на момент создания мы id не знаем,
  // т.к. читаем форму через UI и не парсим URL).
  const createdLogins: string[] = [];

  test.afterAll(async ({ api, adminSession }) => {
    if (!adminSession) return;
    for (const login of createdLogins) {
      try {
        const res = await api.searchRecords(adminSession, 'users', {
          fields: ['id'],
          filter: [['login', '=', login]],
          limit: 1,
        });
        if (res.data.length > 0) {
          await api.deleteRecord(adminSession, 'users', res.data[0].id);
        }
      } catch (e) {
        console.warn(`Cleanup user '${login}' failed:`, e);
      }
    }
  });

  test('создаёт пользователя с обязательными полями name и login', async ({
    page,
  }) => {
    const stamp = Date.now();
    const name = `E2E User ${stamp}`;
    const login = `e2e_user_${stamp}`;
    createdLogins.push(login);

    await page.goto('/users');
    await page.waitForLoadState('domcontentloaded');

    await clickCreate(page);

    await fillByName(page, 'name', name);
    await fillByName(page, 'login', login);

    await clickSave(page);

    if (page.url().endsWith('/create')) {
      await dumpFormState(page, 'create-user');
    }

    // Форма ушла с /create — это и есть признак успешного сохранения
    // (роутер uvideos переключает на /users/<id> после create).
    await expect(page).not.toHaveURL(/\/create$/, { timeout: 10_000 });

    // Имя в форме совпадает с введённым — финальная проверка персистенции.
    const nameInput = page.locator('[data-path="name"]').first();
    await expect(nameInput).toHaveValue(name, { timeout: 10_000 });

    const loginInput = page.locator('[data-path="login"]').first();
    await expect(loginInput).toHaveValue(login, { timeout: 10_000 });
  });

  test('созданный пользователь виден в списке /users', async ({ page }) => {
    const stamp = Date.now();
    const name = `E2E List User ${stamp}`;
    const login = `e2e_list_user_${stamp}`;
    createdLogins.push(login);

    await page.goto('/users');
    await page.waitForLoadState('domcontentloaded');
    await clickCreate(page);

    await fillByName(page, 'name', name);
    await fillByName(page, 'login', login);

    await clickSave(page);
    await expect(page).not.toHaveURL(/\/create$/, { timeout: 10_000 });

    // Возвращаемся в список и проверяем что запись там.
    await page.goto('/users');
    await page.waitForLoadState('domcontentloaded');

    // Ищем по имени — оно уникально благодаря timestamp'у.
    // exact:false на случай если ячейка отрисовывает "Имя <login>" или
    // подобный композит — нам важно лишь чтобы name присутствовал.
    await expect(
      page.getByText(name, { exact: false }).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('нельзя создать второго пользователя с тем же login', async ({
    page,
    api,
    adminSession,
  }) => {
    // Подготовка: сразу через API создадим пользователя, чтобы не зависеть
    // от UI первого теста (тесты serial, но изоляция предпочтительнее).
    const stamp = Date.now();
    const login = `e2e_dup_${stamp}`;
    const name = `E2E Dup ${stamp}`;
    createdLogins.push(login);

    await api.ensureUser(adminSession, {
      login,
      password: 'temporary_pw_123',
      name,
    });

    // Пытаемся создать через UI с тем же login.
    await page.goto('/users');
    await page.waitForLoadState('domcontentloaded');
    await clickCreate(page);

    await fillByName(page, 'name', `${name} duplicate`);
    await fillByName(page, 'login', login);

    await clickSave(page);

    // Ожидаем что форма НЕ перешла с /create (бэкенд должен отклонить).
    // Даём время на сетевой ответ и тост/ошибку.
    await page.waitForTimeout(800);
    await expect(page).toHaveURL(/\/create$/, { timeout: 5_000 });
  });
});
