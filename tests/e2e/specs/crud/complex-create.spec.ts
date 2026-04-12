import { test, expect, Page } from '../../fixtures';

/**
 * "Сложные" e2e-сценарии — создание связанных записей через UI.
 *
 * ВАЖНО про селекторы полей. Ваш FieldWrapper рендерит label через Mantine
 * <Text>, а не семантический <label for="...">. Поэтому page.getByLabel()
 * в Playwright НЕ работает — нет DOM-связи label ↔ input.
 *
 * Используем два подхода:
 * 1. По name-атрибуту: Mantine TextInput прокидывает `name` прямо в <input>,
 *    так что `input[name="fieldName"]` работает надёжно для текстовых полей.
 * 2. Через визуальную близость: ищем контейнер поля с видимым label-текстом,
 *    в нём находим input/combobox. Для Many2one (Combobox).
 */

// ==================== Helpers ====================

/**
 * Находит input по имени поля через data-path атрибут.
 *
 * Mantine form.getInputProps(name) автоматически навешивает data-path="<name>"
 * на все input'ы — это стабильный селектор, не зависящий от label/локализации.
 *
 * Для обычного TextInput возвращает единственный input с data-path.
 * Для Many2one/Combobox возвращает именно видимый input (исключая скрытый
 * hidden-input внутри InputBase display=none).
 */
function fieldByName(page: Page, name: string) {
  // Оба input'а Combobox'а имеют data-path — берём тот что не скрыт через
  // display:none (это visible combobox-input).
  return page
    .locator(`[data-path="${name}"]:not([readonly])`)
    .first();
}

/**
 * Скрытый readonly-input у Combobox тоже имеет data-path. Используем его
 * только как fallback когда нужен именно любой input (для ввода значения в
 * обычном TextInput — readonly там не стоит).
 */
function anyInputByName(page: Page, name: string) {
  return page.locator(`[data-path="${name}"]`).first();
}

async function clickCreate(page: Page) {
  const createBtn = page
    .getByRole('button', { name: /^(создать|create|добавить|\+)$/i })
    .first();
  await createBtn.waitFor({ state: 'visible', timeout: 10_000 });
  await createBtn.click();
  // Ждём URL /create + наличие поля формы — этого достаточно, не ждём networkidle
  await page
    .waitForURL(/\/create$|\/[^/]+\/create/, { timeout: 5_000 })
    .catch(() => {});
  // Ждём что форма отрендерилась — любое поле с data-path видно
  await page
    .locator('[data-path]')
    .first()
    .waitFor({ state: 'attached', timeout: 5_000 });
}

/**
 * Кликает по кнопке сохранения формы.
 *
 * На форме СОЗДАНИЯ у вас ButtonCreate с текстом t('create') = "Создать"
 * (или t('add') = "Добавить" если вложенная O2M-форма).
 * На форме РЕДАКТИРОВАНИЯ — ButtonUpdate с текстом t('save') = "Сохранить"
 * (или "Saving..." когда идёт запрос).
 *
 * Поэтому ищем любой из вариантов. Чтобы не попасть в кнопку "Создать"
 * на странице списка — ограничиваем поиск тулбаром формы (секцией с roles
 * toolbar/region около низа/верха формы). Если тулбара нет, падаем на
 * fallback: берём КНОПКУ с такими текстами в типе submit.
 */
async function clickSave(page: Page) {
  // Ищем кнопку сохранения формы (Toolbar внизу), исключая кнопки внутри
  // O2M-виджетов (Field name="order_line_ids" с showCreate=true тоже имеет
  // кнопку "Создать", но она для добавления строки позиции, не сохранения).
  //
  // Стратегия: среди всех кнопок с текстом "Сохранить"/"Создать"/"Добавить"
  // выбрать первую, которая НЕ находится внутри O2M-виджета (mantine-Paper
  // с классом fieldRelation или рядом с DataTable).
  const btn = await page.evaluateHandle(() => {
    const texts = /^(сохранить|save|saving|создать|create|добавить|add)$/i;
    const allButtons = Array.from(document.querySelectorAll('button'));
    const candidates = allButtons.filter(b => {
      const text = (b.textContent || '').trim();
      if (!texts.test(text)) return false;
      // Должна быть видимой
      const rect = b.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return false;
      // Не должна быть внутри DataTable (O2M-виджет)
      if (b.closest('table, [class*="DataTable"], [class*="fieldRelation"]'))
        return false;
      // Не должна быть внутри открытого диалога
      if (b.closest('[role="dialog"]')) return false;
      return true;
    });
    // Берём ПЕРВУЮ — обычно это Toolbar формы (у вас он сверху рендерится).
    return candidates[0] || null;
  });

  const element = btn.asElement();
  if (!element) {
    throw new Error(
      'clickSave: не найдена кнопка сохранения формы (Toolbar)',
    );
  }
  await element.scrollIntoViewIfNeeded();
  await element.click();
  // Не ждём networkidle — он может висеть из-за WS. Вместо этого
  // отдаём 300мс на начало навигации/обновления и уходим дальше.
  await page.waitForTimeout(300);
}

async function fillByName(page: Page, name: string, value: string) {
  // Для обычных TextInput data-path стоит на единственном input
  const input = page.locator(`[data-path="${name}"]`).first();
  await input.waitFor({ state: 'visible', timeout: 10_000 });
  await input.fill(value);
}

/**
 * Выбор в Many2one Combobox по name-атрибуту поля.
 * В Mantine Combobox два input'а с data-path: скрытый readonly и видимый
 * (для ввода поиска). Берём видимый — он не readonly.
 */
async function pickCombobox(
  page: Page,
  name: string,
  search: string,
  scope?: ReturnType<typeof page.locator>,
) {
  const root = scope ?? page;

  // Сопоставляем скрытый input[data-path=name] с видимым Target Combobox.
  // Оба живут внутри одной обёртки FieldWrapper, которая содержит один
  // input[data-path] И один кликабельный Target.
  // Используем evaluate: находим hidden input, потом в его родителе
  // (несколько уровней вверх) ищем видимую интерактивную кнопку/Target.
  const hidden = root.locator(`[data-path="${name}"]`).first();
  await hidden.waitFor({ state: 'attached', timeout: 10_000 });

  // Через evaluate находим Target: поднимаемся до ближайшего предка,
  // в котором есть видимый элемент с классом mantine-InputBase-input
  // (это Target для Combobox).
  const targetHandle = await hidden.evaluateHandle((el) => {
    // Target в FieldMany2one — <InputBase component="button" type="button">.
    // В DOM это <button type="button"> с классами mantine-Input-input /
    // mantine-InputBase-input. Ищем такой button внутри ближайших предков.
    let node: HTMLElement | null = el as HTMLElement;
    for (let i = 0; i < 8 && node; i++) {
      // button[type="button"] — наш Target
      const buttons = node.querySelectorAll('button[type="button"]');
      for (const btn of Array.from(buttons)) {
        const cls = btn.className || '';
        // Убеждаемся что это Mantine-inputовая кнопка, не action-button
        // (save/cancel имеют другие классы: m_* и mantine-Button-root)
        if (
          cls.includes('mantine-Input') ||
          cls.includes('InputBase') ||
          btn.hasAttribute('aria-haspopup')
        ) {
          const rect = (btn as HTMLElement).getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            return btn;
          }
        }
      }
      node = node.parentElement;
    }
    return null;
  });

  const target = targetHandle.asElement();
  if (!target) {
    throw new Error(`Combobox target for "${name}" not found in DOM`);
  }

  await target.click();

  // Поиск в Combobox.Search внутри dropdown (если нужен)
  if (search) {
    const searchInput = page.getByPlaceholder(/поиск/i).first();
    if (await searchInput.isVisible({ timeout: 500 }).catch(() => false)) {
      await searchInput.fill(search);
    }
  }

  // Ждём появления видимой опции. Используем :visible чтобы игнорировать
  // опции от предыдущего Combobox, которые ещё остаются в DOM во время
  // анимации закрытия (Mantine удаляет их с задержкой).
  const visibleOptions = page.locator('[role="option"]:visible');
  await visibleOptions.first().waitFor({ state: 'visible', timeout: 5_000 });

  const targetOption = search
    ? (await visibleOptions
          .filter({ hasText: new RegExp(search, 'i') })
          .count()) > 0
      ? visibleOptions.filter({ hasText: new RegExp(search, 'i') }).first()
      : visibleOptions.first()
    : visibleOptions.first();

  await targetOption.click({ timeout: 5_000 });

  // Ждём что видимых опций больше нет — защита от race с следующим Combobox.
  // Используем :visible вместо полного удаления из DOM — быстрее.
  await page
    .locator('[role="option"]:visible')
    .first()
    .waitFor({ state: 'hidden', timeout: 1_500 })
    .catch(() => {});
}

// ==================== Tests ====================

test.describe('test_create_complex', () => {
  test.describe.configure({ mode: 'serial' });

  test('sale with order line — создать заказ и позицию', async ({ page }) => {
    const saleName = `E2E-Sale-${Date.now()}`;

    await page.goto('/sales');
    await page.waitForLoadState('domcontentloaded');
    await clickCreate(page);

    await fillByName(page, 'name', saleName);

    // Клиент (partner_id) — Many2one
    await pickCombobox(page, 'partner_id', '');

    // Стадия — обязательное поле
    await pickCombobox(page, 'stage_id', '');

    await clickSave(page);

    // Если форма осталась на /create — дампим ошибки валидации для отладки
    if (await page.url().endsWith('/create')) {
      const errors = await page
        .locator(
          '.mantine-TextInput-error, [class*="error"], [data-error="true"]',
        )
        .allTextContents();
      const values = await page.evaluate(() => {
        const inputs = document.querySelectorAll('[data-path]');
        return Array.from(inputs).map(el => ({
          path: el.getAttribute('data-path'),
          value: (el as HTMLInputElement).value,
        }));
      });
      console.log('Form still on /create. Field errors:', errors);
      console.log('Field values:', JSON.stringify(values, null, 2));
    }

    await expect(page).not.toHaveURL(/\/create$/, { timeout: 10_000 });

    // Вкладка позиций заказа
    const linesTab = page
      .getByRole('tab', { name: /позици|lines|товар/i })
      .first();
    if (await linesTab.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await linesTab.click();
    }

    // Кнопка "Создать" для O2M order_line_ids. В DOM это Button с текстом
    // "Создать" и IconPlus. На странице уже есть другая "Создать" (ButtonCreate
    // на форме заказа внизу) — берём ту что внутри таба позиций. Надёжнее —
    // найти кнопку с IconPlus внутри Group рядом с DataTable.
    // В ButtonCreate.tsx: текст кнопки сохранения формы = t('create') = "Создать"
    // А в O2M виджете — отдельная кнопка "Создать" открывает модалку.
    // К этому моменту мы уже сохранили заказ, URL перешёл на /sales/<id>,
    // тулбар формы теперь показывает "Сохранить" (ButtonUpdate), поэтому
    // на странице единственная кнопка "Создать" — это O2M-кнопка.
    const addLineBtn = page
      .getByRole('button', { name: /^создать$|^create$/i })
      .first();
    await addLineBtn.waitFor({ state: 'visible', timeout: 10_000 });
    await addLineBtn.click();

    // Открылась модалка с заголовком "Создание: sale_line".
    // Заполняем обязательные поля позиции: product_id и количество.
    const dialog = page.getByRole('dialog').first();
    await dialog.waitFor({ state: 'visible', timeout: 10_000 });

    // Внутри модалки ищем поля по data-path. Они тоже рендерятся с
    // form.getInputProps, так что data-path работает и здесь.
    // Выбираем продукт в модалке — первый доступный.
    // pickCombobox уже умеет скоупить поиск в dialog.
    await pickCombobox(page, 'product_id', '', dialog);

    // Количество
    const qtyInput = dialog.locator('[data-path="product_uom_qty"]').first();
    if (await qtyInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await qtyInput.fill('1');
    }

    // Кнопка сохранения в модалке = "Добавить".
    // В ButtonCreate.tsx при вложенной O2M-форме текст = t('add') = "Добавить",
    // а не "Создать". Ищем строго внутри dialog scope.
    const dialogSaveBtn = dialog
      .getByRole('button', { name: /^(добавить|add)$/i })
      .first();
    await dialogSaveBtn.waitFor({ state: 'visible', timeout: 10_000 });
    await dialogSaveBtn.click();

    // Ждём закрытия модалки — диалог больше не должен быть видимым
    await dialog.waitFor({ state: 'hidden', timeout: 5_000 }).catch(() => {});

    // Модалка должна закрыться, позиция появиться в таблице заказа.
    // Финальный clickSave — кнопка "Сохранить" формы заказа (теперь ButtonUpdate).
    await clickSave(page);

    // Проверяем что заказ создался:
    // 1. URL ушёл с /create (уже на /sales/<id>)
    // 2. Имя заказа видно либо в input[data-path="name"], либо где-то в тексте.
    await expect(page).not.toHaveURL(/\/create$/, { timeout: 10_000 });

    const nameInput = page.locator('[data-path="name"]').first();
    await expect(nameInput).toHaveValue(saleName, { timeout: 10_000 });
  });

  test('partners hierarchy — создать двух партнёров и связать child-parent', async ({
    page,
  }) => {
    const parentName = `E2E-Parent-${Date.now()}`;
    const childName = `E2E-Child-${Date.now()}`;

    await page.goto('/partners');
    await page.waitForLoadState('domcontentloaded');
    await clickCreate(page);
    await fillByName(page, 'name', parentName);
    await clickSave(page);
    await expect(page).not.toHaveURL(/\/create$/, { timeout: 10_000 });

    await page.goto('/partners');
    await page.waitForLoadState('domcontentloaded');
    await clickCreate(page);
    await fillByName(page, 'name', childName);

    const commonTab = page
      .getByRole('tab', { name: /общие|common/i })
      .first();
    if (await commonTab.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await commonTab.click();
    }

    await pickCombobox(page, 'parent_id', parentName);

    await clickSave(page);
    await expect(page).not.toHaveURL(/\/create$/, { timeout: 10_000 });

    await page.goto('/partners');
    await page.waitForLoadState('domcontentloaded');

    await page.getByText(parentName, { exact: false }).first().click();

    const childrenTab = page
      .getByRole('tab', { name: /дочерн|child/i })
      .first();
    await childrenTab.waitFor({ state: 'visible', timeout: 10_000 });
    await childrenTab.click();

    await expect(
      page.getByText(childName, { exact: false }).first(),
    ).toBeVisible({ timeout: 10_000 });
  });
});
