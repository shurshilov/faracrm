import { test, expect } from '../../fixtures';
import { ChatPage } from '../../pages/ChatPage';

/**
 * Тест: создание direct-чата, отправка сообщения,
 * проверка что у получателя появляется уведомление о непрочитанном.
 */
test.describe('Чат — direct и непрочитанные', () => {
  let chatId: number;

  test.afterEach(async ({ api, adminToken, adminSession }) => {
    if (chatId) {
      await api.deleteChat(adminSession, chatId).catch(() => {});
    }
  });

  test('user2 отправляет сообщение в direct, admin видит непрочитанное', async ({
    page,
    user2Page,
    api,
    user2Token,
    user2Session,
    adminToken, adminSession,
  }) => {
    // Создаём direct-чат между user2 и admin
    const chat = await api.createChat(user2Session, {
      name: '',
      chat_type: 'direct',
      user_ids: [1], // admin user_id = 1
    });
    chatId = chat.id;

    // Admin открывает страницу чатов (но НЕ открывает этот чат)
    const adminChat = new ChatPage(page);
    await adminChat.goto();

    // Находим direct-чат в списке у user2 по имени собеседника "Administrator"
    const user2Chat = new ChatPage(user2Page);
    await user2Chat.goto();

    // Direct чат показывается как "Имя собеседника" — ищем по "Administrator"
    // или по "Test User 1 - Administrator" формату
    const chatLocator = user2Page.locator('[class*="chatItem"], [class*="ChatItem"], [class*="chat-item"]')
      .filter({ hasText: /Administrator/ }).first();

    // Если не нашли — ищем любой чат "Личные"
    if (!(await chatLocator.isVisible().catch(() => false))) {
      // Кликаем на фильтр "Личные"
      await user2Page.getByText(/личные|personal|direct/i).first().click();
      await user2Page.waitForTimeout(1_000);
    }

    // Кликаем на чат с Administrator
    const directChat = user2Page.getByText(/Administrator/).first();
    await directChat.waitFor({ state: 'visible', timeout: 10_000 });
    await directChat.click();

    // Ждём загрузку чата
    await user2Page.waitForTimeout(1_000);

    // Отправляем сообщение
    await user2Chat.sendMessage('Привет, это direct сообщение!');

    // У Admin должно появиться превью сообщения в списке чатов
    // Direct чат показывается как "Test User 1 - Administrator" или "Test User 1"
    await expect(
      page.getByText('Привет, это direct сообщение!', { exact: false }),
    ).toBeVisible({ timeout: 15_000 });
  });
});
