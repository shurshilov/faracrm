import { test, expect } from '../../fixtures';
import { ChatPage } from '../../pages/ChatPage';

test.describe('Чат — UI отправка сообщений', () => {

  let chatId: number;
  let chatName: string;

  test.beforeEach(async ({ api, adminToken, user2Session }) => {
    chatName = `E2E Chat ${Date.now()}`;
    const result = await api.createChat(adminToken, {
      name: chatName,
      user_ids: [user2Session.user_id.id],
    });
    chatId = result.id;
  });

  test.afterEach(async ({ api, adminToken }) => {
    if (chatId) {
      await api.deleteChat(adminToken, chatId).catch(() => {});
    }
  });

  test('отправка сообщения через UI', async ({ page }) => {
    const chat = new ChatPage(page);
    await chat.goto();
    await chat.openChat(chatName);
    await chat.sendMessage('Привет из E2E теста!');
    await chat.expectMessageVisible('Привет из E2E теста!');
  });

  test('отправка нескольких сообщений сохраняет порядок', async ({ page }) => {
    const chat = new ChatPage(page);
    await chat.goto();
    await chat.openChat(chatName);

    await chat.sendMessage('Первое сообщение');
    await chat.sendMessage('Второе сообщение');
    await chat.sendMessage('Третье сообщение');

    const messages = await chat.allMessages.allTextContents();
    const texts = messages.join(' ');
    expect(texts).toContain('Первое');
    expect(texts).toContain('Второе');
    expect(texts).toContain('Третье');
    // Порядок: третье должно быть после первого
    expect(texts.indexOf('Первое')).toBeLessThan(texts.indexOf('Третье'));
  });

  test('редактирование своего сообщения', async ({ page }) => {
    const chat = new ChatPage(page);
    await chat.goto();
    await chat.openChat(chatName);
    await chat.sendMessage('Оригинальный текст');
    await chat.editMessage('Оригинальный текст', 'Отредактированный текст');
    await chat.expectMessageVisible('Отредактированный текст');
    await chat.expectMessageNotVisible('Оригинальный текст');
  });

  test('удаление своего сообщения', async ({ page }) => {
    const chat = new ChatPage(page);
    await chat.goto();
    await chat.openChat(chatName);
    await chat.sendMessage('Удали меня');
    await chat.expectMessageVisible('Удали меня');
    await chat.deleteMessage('Удали меня');
    await chat.expectMessageNotVisible('Удали меня');
  });

  test('создание группового чата через UI', async ({ page }) => {
    const chat = new ChatPage(page);
    await chat.goto();

    const newChatName = `UI Group ${Date.now()}`;
    await chat.createGroupChat(newChatName);
    await chat.expectChatInList(newChatName);
  });
});
