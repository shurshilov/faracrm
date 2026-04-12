// import { test, expect, Page } from '../../fixtures';

// /**
//  * "Сложные" e2e-сценарии — создание связанных записей через UI.
//  *
//  * ВАЖНО про селекторы полей. Ваш FieldWrapper рендерит label через Mantine
//  * <Text>, а не семантический <label for="...">. Поэтому page.getByLabel()
//  * в Playwright НЕ работает — нет DOM-связи label ↔ input.
//  *
//  * Используем два подхода:
//  * 1. По name-атрибуту: Mantine TextInput прокидывает `name` прямо в <input>,
//  *    так что `input[name="fieldName"]` работает надёжно для текстовых полей.
//  * 2. Через визуальную близость: ищем контейнер поля с видимым label-текстом,
//  *    в нём находим input/combobox. Для Many2one (Combobox).
//  */

// // ==================== Helpers ====================

// /**
//  * Находит input по имени поля через data-path атрибут.
//  *
//  * Mantine form.getInputProps(name) автоматически навешивает data-path="<name>"
//  * на все input'ы — это стабильный селектор, не зависящий от label/локализации.
//  *
//  * Для обычного TextInput возвращает единственный input с data-path.
//  * Для Many2one/Combobox возвращает именно видимый input (исключая скрытый
//  * hidden-input внутри InputBase display=none).
//  */
// function fieldByName(page: Page, name: string) {
//   // Оба input'а Combobox'а имеют data-path — берём тот что не скрыт через
//   // display:none (это visible combobox-input).
//   return page
//     .locator(`[data-path="${name}"]:not([readonly])`)
//     .first();
// }

// /**
//  * Скрытый readonly-input у Combobox тоже имеет data-path. Используем его
//  * только как fallback когда нужен именно любой input (для ввода значения в
//  * обычном TextInput — readonly там не стоит).
//  */
// function anyInputByName(page: Page, name: string) {
//   return page.locator(`[data-path="${name}"]`).first();
// }

// async function clickCreate(page: Page) {
//   const createBtn = page
//     .getByRole('button', { name: /^(создать|create|добавить|\+)$/i })
//     .first();
//   await createBtn.waitFor({ state: 'visible', timeout: 10_000 });
//   await createBtn.click();
//   await page
//     .waitForURL(/\/create$|\/[^/]+\/create/, { timeout: 5_000 })
//     .catch(() => {});
//   await page.waitForLoadState('networkidle');
// }

// /**
//  * Кликает по кнопке сохранения формы.
//  *
//  * На форме СОЗДАНИЯ у вас ButtonCreate с текстом t('create') = "Создать"
//  * (или t('add') = "Добавить" если вложенная O2M-форма).
//  * На форме РЕДАКТИРОВАНИЯ — ButtonUpdate с текстом t('save') = "Сохранить"
//  * (или "Saving..." когда идёт запрос).
//  *
//  * Поэтому ищем любой из вариантов. Чтобы не попасть в кнопку "Создать"
//  * на странице списка — ограничиваем поиск тулбаром формы (секцией с roles
//  * toolbar/region около низа/верха формы). Если тулбара нет, падаем на
//  * fallback: берём КНОПКУ с такими текстами в типе submit.
//  */
// async function clickSave(page: Page) {
//   const saveBtn = page
//     .getByRole('button', {
//       name: /^(сохранить|save|saving|создать|create|добавить|add)$/i,
//     })
//     .last(); // .last() чтобы попасть в кнопку формы внизу, а не в шапке списка
//   await saveBtn.waitFor({ state: 'visible', timeout: 10_000 });
//   await saveBtn.click();
//   await page.waitForLoadState('networkidle');
//   await page.waitForTimeout(500);
// }

// async function fillByName(page: Page, name: string, value: string) {
//   // Для обычных TextInput data-path стоит на единственном input
//   const input = page.locator(`[data-path="${name}"]`).first();
//   await input.waitFor({ state: 'visible', timeout: 10_000 });
//   await input.fill(value);
// }

// /**
//  * Выбор в Many2one Combobox по name-атрибуту поля.
//  * В Mantine Combobox два input'а с data-path: скрытый readonly и видимый
//  * (для ввода поиска). Берём видимый — он не readonly.
//  */
// async function pickCombobox(
//   page: Page,
//   name: string,
//   search: string,
// ) {
//   const visibleInput = page
//     .locator(`[data-path="${name}"]:not([readonly])`)
//     .first();
//   await visibleInput.waitFor({ state: 'visible', timeout: 10_000 });
//   await visibleInput.click();
//   await page.waitForTimeout(300);

//   if (search) {
//     await visibleInput.fill(search).catch(() => {});
//     await page.waitForTimeout(500);
//   }

//   const option = search
//     ? page
//         .locator('[role="option"]')
//         .filter({ hasText: new RegExp(search, 'i') })
//         .first()
//     : page.locator('[role="option"]').first();

//   if (await option.isVisible({ timeout: 3_000 }).catch(() => false)) {
//     await option.click();
//   } else {
//     await page.locator('[role="option"]').first().click();
//   }
// }

// // ==================== Tests ====================

// test.describe('test_create_complex', () => {
//   test.describe.configure({ mode: 'serial' });

//   test('sale with order line — создать заказ и позицию', async ({ page }) => {
//     const saleName = `E2E-Sale-${Date.now()}`;

//     await page.goto('/sales');
//     await page.waitForLoadState('networkidle');
//     await clickCreate(page);

//     await fillByName(page, 'name', saleName);

//     // Клиент (partner_id) — Many2one
//     await pickCombobox(page, 'partner_id', '');

//     // Стадия — обязательное поле
//     await pickCombobox(page, 'stage_id', '');

//     await clickSave(page);
//     await expect(page).not.toHaveURL(/\/create$/, { timeout: 10_000 });

//     // Вкладка позиций заказа
//     const linesTab = page
//       .getByRole('tab', { name: /позици|lines|товар/i })
//       .first();
//     if (await linesTab.isVisible({ timeout: 3_000 }).catch(() => false)) {
//       await linesTab.click();
//       await page.waitForTimeout(500);
//     }

//     // Кнопка "Создать" для O2M order_line_ids. В DOM это Button с текстом
//     // "Создать" и IconPlus. На странице уже есть другая "Создать" (ButtonCreate
//     // на форме заказа внизу) — берём ту что внутри таба позиций. Надёжнее —
//     // найти кнопку с IconPlus внутри Group рядом с DataTable.
//     const addLineBtn = page
//       .locator('button:has(svg)')
//       .filter({ hasText: /^создать$|^create$/i })
//       .first();
//     await addLineBtn.waitFor({ state: 'visible', timeout: 10_000 });
//     await addLineBtn.click();

//     // Открылась модалка с заголовком "Создание: sale_line".
//     // Заполняем обязательные поля позиции: product_id и количество.
//     const dialog = page.getByRole('dialog').first();
//     await dialog.waitFor({ state: 'visible', timeout: 10_000 });

//     // Внутри модалки ищем поля по data-path. Они тоже рендерятся с
//     // form.getInputProps, так что data-path работает и здесь.
//     const productInput = dialog
//       .locator('[data-path="product_id"]:not([readonly])')
//       .first();
//     await productInput.waitFor({ state: 'visible', timeout: 10_000 });

//     // Кликаем по input чтобы открыть Combobox и сфокусировать внутренний
//     // поисковый input (см. FieldMany2one: combobox.focusSearchInput()).
//     await productInput.click();
//     await productInput.focus();
//     await page.waitForTimeout(500);

//     // Если dropdown не открылся — нажимаем клавишу чтобы триггернуть
//     // onChange поиска (Mantine Combobox открывается при вводе).
//     const firstOption = page.locator('[role="option"]').first();
//     if (!(await firstOption.isVisible({ timeout: 1_000 }).catch(() => false))) {
//       // Пробуем ввести пробел — это откроет dropdown без фильтрации по имени
//       await productInput.pressSequentially(' ', { delay: 50 });
//       await page.waitForTimeout(300);
//       // Убираем пробел обратно чтобы не исказить фильтр
//       await productInput.press('Backspace');
//       await page.waitForTimeout(500);
//     }

//     // Берём первую доступную опцию
//     await firstOption.waitFor({ state: 'visible', timeout: 5_000 });
//     await firstOption.click();
//     await page.waitForTimeout(300);

//     // Количество
//     const qtyInput = dialog.locator('[data-path="product_uom_qty"]').first();
//     if (await qtyInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
//       await qtyInput.fill('1');
//     }

//     // Кнопка "Создать" внутри модалки — сохраняет позицию
//     const dialogSaveBtn = dialog
//       .getByRole('button', { name: /^(создать|create|добавить|add)$/i })
//       .last();
//     await dialogSaveBtn.waitFor({ state: 'visible', timeout: 10_000 });
//     await dialogSaveBtn.click();
//     await page.waitForTimeout(800);

//     // Модалка должна закрыться, позиция появиться в таблице заказа.
//     // Финальный clickSave — кнопка "Сохранить" формы заказа (теперь ButtonUpdate).
//     await clickSave(page);

//     await expect(page.getByText(saleName).first()).toBeVisible({
//       timeout: 10_000,
//     });
//   });

//   test('partners hierarchy — создать двух партнёров и связать child-parent', async ({
//     page,
//   }) => {
//     const parentName = `E2E-Parent-${Date.now()}`;
//     const childName = `E2E-Child-${Date.now()}`;

//     await page.goto('/partners');
//     await page.waitForLoadState('networkidle');
//     await clickCreate(page);
//     await fillByName(page, 'name', parentName);
//     await clickSave(page);
//     await expect(page).not.toHaveURL(/\/create$/, { timeout: 10_000 });

//     await page.goto('/partners');
//     await page.waitForLoadState('networkidle');
//     await clickCreate(page);
//     await fillByName(page, 'name', childName);

//     const commonTab = page
//       .getByRole('tab', { name: /общие|common/i })
//       .first();
//     if (await commonTab.isVisible({ timeout: 3_000 }).catch(() => false)) {
//       await commonTab.click();
//       await page.waitForTimeout(300);
//     }

//     await pickCombobox(page, 'parent_id', parentName);

//     await clickSave(page);
//     await expect(page).not.toHaveURL(/\/create$/, { timeout: 10_000 });

//     await page.goto('/partners');
//     await page.waitForLoadState('networkidle');

//     await page.getByText(parentName, { exact: false }).first().click();
//     await page.waitForLoadState('networkidle');

//     const childrenTab = page
//       .getByRole('tab', { name: /дочерн|child/i })
//       .first();
//     await childrenTab.waitFor({ state: 'visible', timeout: 10_000 });
//     await childrenTab.click();
//     await page.waitForTimeout(500);

//     await expect(
//       page.getByText(childName, { exact: false }).first(),
//     ).toBeVisible({ timeout: 10_000 });
//   });
// });
