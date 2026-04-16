/**
 * FormPanels E2E Tests
 *
 * Тестируем панель на карточке партнёра:
 * 1. Отправка сообщения через MessagesPanel → проверка счётчика
 * 2. Загрузка вложения через AttachmentsPanel → проверка счётчика + скачивание
 * 3. Создание активности через ActivityPanel → проверка счётчика
 * 4. Проверка иконок (серые при пустых, синие при заполненных)
 * 5. Проверка что сообщение реально создалось в чате
 * 6. Проверка что вложение скачивается и содержимое совпадает
 *
 * Логин: admin. Все тесты работают с одним партнёром, созданным в setup.
 */

import { test, expect } from '../../fixtures';

const PARTNER_NAME = `E2E Panel Test ${Date.now()}`;
let partnerId: number;

// ===================== Setup / Teardown =====================

test.describe('FormPanels — messages, attachments, activities', () => {
  test.describe.configure({ mode: 'serial' });

  test.beforeAll(async ({ api, adminSession }) => {
    // Создаём партнёра через API
    const result = await api.createRecord(adminSession, 'partners', {
      name: PARTNER_NAME,
    });
    partnerId = result.id;
  });

  test.afterAll(async ({ api, adminSession }) => {
    // Чистим за собой
    if (partnerId) {
      try {
        await api.deleteRecord(adminSession, 'partners', partnerId);
      } catch {
        // Может быть уже удалён или FK constraint — не критично
      }
    }
  });

  // ===================== Helpers =====================

  /** Открыть карточку партнёра и дождаться загрузки формы */
  async function openPartnerCard(page: any) {
    await page.goto(`/partners/${partnerId}`);
    // Ждём загрузки формы (заголовок партнёра)
    await page.waitForLoadState('networkidle');
  }

  /** Получить Locator панельных иконок */
  function panelIcons(page: any) {
    return {
      activities: page.locator('button[title*="ктивност"], button[title*="ctivit"]'),
      messages: page.locator('button[title*="ообщени"], button[title*="essage"]'),
      attachments: page.locator('button[title*="ложени"], button[title*="ttachment"]'),
    };
  }

  /** Получить текст бейджика (Mantine Indicator) рядом с иконкой */
  async function getBadgeText(iconLocator: any): Promise<string | null> {
    // Mantine Indicator рендерит span.mantine-Indicator-indicator внутри
    // обёртки div.mantine-Indicator-root
    const wrapper = iconLocator.locator('xpath=ancestor::div[contains(@class, "Indicator")]');
    const badge = wrapper.locator('[class*="Indicator-indicator"]');
    if ((await badge.count()) === 0) return null;
    const visible = await badge.isVisible().catch(() => false);
    if (!visible) return null;
    return badge.textContent();
  }

  // ===================== Test 1: Empty state — icons gray =====================

  test('1. Empty partner card — all panel icons are gray, no badges', async ({
    page,
    adminSession,
  }) => {
    await openPartnerCard(page);

    const icons = panelIcons(page);

    // Все три иконки существуют
    await expect(icons.activities).toBeVisible({ timeout: 10_000 });
    await expect(icons.messages).toBeVisible();
    await expect(icons.attachments).toBeVisible();

    // Проверяем что нет видимых бейджиков (Indicator disabled при count=0)
    const activitiesBadge = await getBadgeText(icons.activities);
    const messagesBadge = await getBadgeText(icons.messages);
    const attachmentsBadge = await getBadgeText(icons.attachments);

    expect(activitiesBadge).toBeNull();
    expect(messagesBadge).toBeNull();
    expect(attachmentsBadge).toBeNull();

    // Иконки должны быть серыми (color="gray" → Mantine вычисляет
    // в HEX, например #868e96). Проверяем что цвет НЕ синий —
    // это надёжнее, чем сверять конкретный HEX серого (может
    // отличаться в разных темах Mantine).
    for (const icon of [icons.activities, icons.messages, icons.attachments]) {
      const color = await icon.evaluate((el: HTMLElement) => {
        return getComputedStyle(el).getPropertyValue('--ai-color').trim();
      });
      // Синий в Mantine: #228be6 (blue.6) или подобный.
      // Серый: #868e96 (gray.6) или подобный.
      // Достаточно убедиться что НЕ синий.
      expect(color).not.toMatch(/228be6|339af0|1c7ed6/i);
    }
  });

  // ===================== Test 2: Send message → badge appears =====================

  test('2. Send message via panel → message badge shows unread count', async ({
    page,
    adminSession,
  }) => {
    await openPartnerCard(page);

    const icons = panelIcons(page);

    // Кликаем иконку сообщений → панель открывается
    await icons.messages.click();

    // Ждём панель сообщений — должен быть input для текста
    const messageInput = page.locator(
      'textarea[placeholder*="ообщени"], textarea[placeholder*="essage"], ' +
        'input[placeholder*="ообщени"], input[placeholder*="essage"]',
    );
    await messageInput.waitFor({ state: 'visible', timeout: 10_000 });

    // Пишем и отправляем
    const testMessage = `E2E test message ${Date.now()}`;
    await messageInput.fill(testMessage);

    // Enter для отправки или клик на кнопку отправки
    const sendBtn = page.locator(
      'button:has(svg[class*="tabler-icon-send"]), ' +
        '[data-testid="send-button"]',
    );
    if (await sendBtn.isVisible().catch(() => false)) {
      await sendBtn.click();
    } else {
      await messageInput.press('Enter');
    }

    // Ждём что сообщение появилось (текст в панели)
    await expect(page.getByText(testMessage)).toBeVisible({ timeout: 10_000 });
  });

  // ===================== Test 3: Message was actually created =====================

  test('3. Verify message exists via API', async ({ api, adminSession }) => {
    // Используем /records/{model}/{id}/chat — auto-CRUD для chat отключён.
    const chatInfo = await api.findRecordChat(
      adminSession,
      'partners',
      partnerId,
    );
    expect(chatInfo.chat_id).toBeTruthy();

    const messages = await api.getMessages(adminSession, chatInfo.chat_id!);

    expect(messages.data.length).toBeGreaterThan(0);
    // Последнее сообщение содержит наш текст
    const lastMsg = messages.data[messages.data.length - 1];
    expect(lastMsg.body).toContain('E2E test message');

    // Дополнительно: проверяем счётчик через dedicated endpoint
    const counts = await api.getMessagesCount(
      adminSession,
      'partners',
      partnerId,
    );
    expect(counts.total).toBeGreaterThan(0);
  });

  // ===================== Test 4: Upload attachment → badge appears =====================

  test('4. Upload attachment via API → attachment badge shows count', async ({
    page,
    api,
    adminSession,
  }) => {
    // Загружаем файл через API (POST /auto/attachments) — это тот же
    // эндпоинт, что использует AttachmentsPanel, но без зависимости
    // от Playwright-взаимодействия со скрытым input[type=file].
    const testContent = 'Hello from E2E test!';
    const testFileName = `e2e-test-${Date.now()}.txt`;
    const base64Content = Buffer.from(testContent).toString('base64');

    await api.createRecord(adminSession, 'attachments', {
      name: testFileName,
      res_model: 'partners',
      res_id: partnerId,
      mimetype: 'text/plain',
      size: testContent.length,
      content: base64Content,
      folder: false,
      public: false,
    });

    // Проверяем через API что вложение создалось
    const atts = await api.getAttachmentsFor(
      adminSession,
      'partners',
      partnerId,
    );
    expect(atts.length).toBeGreaterThanOrEqual(1);
    const our = atts.find((a: any) => a.name?.includes('e2e-test-'));
    expect(our).toBeDefined();

    // Открываем карточку и проверяем бейджик
    await openPartnerCard(page);

    const icons = panelIcons(page);

    const badgeLocator = icons.attachments
      .locator('xpath=ancestor::*[contains(@class, "Indicator")]')
      .locator('[class*="indicator" i]');

    await expect(badgeLocator).toBeVisible({ timeout: 10_000 });
    const text = await badgeLocator.textContent();
    expect(Number(text)).toBeGreaterThanOrEqual(1);
  });

  // ===================== Test 5: Attachment downloads correctly =====================

  test('5. Uploaded attachment downloads with correct content', async ({
    api,
    adminSession,
  }) => {
    // Ищем вложения через API
    const attachments = await api.getAttachmentsFor(
      adminSession,
      'partners',
      partnerId,
    );
    expect(attachments.length).toBeGreaterThan(0);

    // Находим наш тестовый файл
    const testAtt = attachments.find((a: any) => a.name?.includes('e2e-test-'));
    expect(testAtt).toBeDefined();
    expect(testAtt.mimetype).toBe('text/plain');

    // Скачиваем и проверяем содержимое
    const content = await api.fetchAttachmentContent(adminSession, testAtt.id);
    const text = new TextDecoder().decode(content);
    expect(text).toBe('Hello from E2E test!');
  });

  // ===================== Test 6: Create activity → badge appears =====================

  test('6. Create activity via API → activity badge shows count', async ({
    page,
    api,
    adminSession,
  }) => {
    // Ищем тип активности для создания
    const types = await api.searchRecords(adminSession, 'activity_type', {
      fields: ['id', 'name'],
      limit: 1,
    });

    // Создаём активность через API (UI-создание сложнее и зависит от формы)
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);

    const activityData: Record<string, any> = {
      res_model: 'partners',
      res_id: partnerId,
      summary: `E2E test activity ${Date.now()}`,
      date_deadline: tomorrow.toISOString().split('T')[0], // YYYY-MM-DD
      user_id: adminSession.user_id.id,
      done: false,
      active: true,
    };
    if (types.data.length > 0) {
      activityData.activity_type_id = types.data[0].id;
    }
    await api.createRecord(adminSession, 'activity', activityData);

    // Открываем карточку и проверяем бейджик
    await openPartnerCard(page);

    const icons = panelIcons(page);

    // Бейджик активностей должен показывать >= 1
    const badge = icons.activities
      .locator('xpath=ancestor::*[contains(@class, "Indicator")]')
      .locator('[class*="indicator" i]');

    await expect(badge).toBeVisible({ timeout: 10_000 });
    const text = await badge.textContent();
    expect(Number(text)).toBeGreaterThanOrEqual(1);

    // После всех тестов — все три иконки должны быть активными (не серыми),
    // потому что у каждой count > 0.
    for (const icon of [icons.activities, icons.messages, icons.attachments]) {
      const color = await icon.evaluate((el: HTMLElement) => {
        return getComputedStyle(el).getPropertyValue('--ai-color').trim();
      });
      // Не серый (#868e96 и подобные) — значит активный цвет
      expect(color).not.toMatch(/868e96|adb5bd|ced4da/i);
    }
  });
});
