import { test, expect } from '../../fixtures';
import { ChatPage } from '../../pages/ChatPage';

/**
 * Multi-tab тесты — два браузерных окна, проверка real-time UI.
 *
 * Это уникальная возможность Playwright: два пользователя в двух вкладках
 * одновременно. Cypress так не умеет.
 */
test.describe('Чат — real-time между двумя браузерами', () => {
  let chatId: number;
  let chatName: string;

  test.beforeEach(async ({ api, adminToken, user2Session }) => {
    chatName = `MultiTab ${Date.now()}`;
    const chat = await api.createChat(adminToken, {
      name: chatName,
      user_ids: [user2Session.user_id.id],
    });
    chatId = chat.id;
  });

  test.afterEach(async ({ api, adminToken }) => {
    await api.deleteChat(adminToken, chatId).catch(() => {});
  });

  test('сообщение admin появляется у user2 в реальном времени', async ({
    page,
    user2Page,
  }) => {
    // Admin открывает чат
    const adminChat = new ChatPage(page);
    await adminChat.goto();
    await adminChat.openChat(chatName);

    // User2 открывает тот же чат
    const user2Chat = new ChatPage(user2Page);
    await user2Chat.goto();
    await user2Chat.openChat(chatName);

    // Admin отправляет сообщение
    await adminChat.sendMessage('Видишь это сообщение?');

    // User2 видит сообщение в реальном времени (без перезагрузки)
    await user2Chat.expectMessageVisible('Видишь это сообщение?');
  });

  test('сообщение user2 появляется у admin в реальном времени', async ({
    page,
    user2Page,
  }) => {
    const adminChat = new ChatPage(page);
    await adminChat.goto();
    await adminChat.openChat(chatName);

    const user2Chat = new ChatPage(user2Page);
    await user2Chat.goto();
    await user2Chat.openChat(chatName);

    await user2Chat.sendMessage('Ответ от user2');
    await adminChat.expectMessageVisible('Ответ от user2');
  });

  test('диалог из нескольких сообщений синхронизируется', async ({
    page,
    user2Page,
  }) => {
    const adminChat = new ChatPage(page);
    await adminChat.goto();
    await adminChat.openChat(chatName);

    const user2Chat = new ChatPage(user2Page);
    await user2Chat.goto();
    await user2Chat.openChat(chatName);

    // Диалог
    await adminChat.sendMessage('Привет!');
    await user2Chat.expectMessageVisible('Привет!');

    await user2Chat.sendMessage('Здравствуйте!');
    await adminChat.expectMessageVisible('Здравствуйте!');

    await adminChat.sendMessage('Как дела?');
    await user2Chat.expectMessageVisible('Как дела?');

    // Оба видят все 3 сообщения
    const adminMessages = await adminChat.allMessages.count();
    const user2Messages = await user2Chat.allMessages.count();
    expect(adminMessages).toBeGreaterThanOrEqual(3);
    expect(user2Messages).toBeGreaterThanOrEqual(3);
  });

  test('удалённое сообщение исчезает у другого пользователя', async ({
    page,
    user2Page,
  }) => {
    const adminChat = new ChatPage(page);
    await adminChat.goto();
    await adminChat.openChat(chatName);

    const user2Chat = new ChatPage(user2Page);
    await user2Chat.goto();
    await user2Chat.openChat(chatName);

    // Admin отправляет и удаляет
    await adminChat.sendMessage('Сейчас удалю');
    await user2Chat.expectMessageVisible('Сейчас удалю');

    await adminChat.deleteMessage('Сейчас удалю');

    // У user2 тоже должно исчезнуть
    await user2Chat.expectMessageNotVisible('Сейчас удалю');
  });

  test('отредактированное сообщение обновляется у другого пользователя', async ({
    page,
    user2Page,
  }) => {
    const adminChat = new ChatPage(page);
    await adminChat.goto();
    await adminChat.openChat(chatName);

    const user2Chat = new ChatPage(user2Page);
    await user2Chat.goto();
    await user2Chat.openChat(chatName);

    await adminChat.sendMessage('Старый текст');
    await user2Chat.expectMessageVisible('Старый текст');

    await adminChat.editMessage('Старый текст', 'Новый текст');

    await user2Chat.expectMessageVisible('Новый текст');
    await user2Chat.expectMessageNotVisible('Старый текст');
  });

  test('новый чат появляется в списке у user2 без перезагрузки', async ({
    page,
    user2Page,
    api,
    adminToken,
    user2Session,
  }) => {
    // user2 открывает страницу чатов
    const user2Chat = new ChatPage(user2Page);
    await user2Chat.goto();

    // admin создаёт новый чат с user2 через API
    const newChatName = `Realtime New ${Date.now()}`;
    const newChat = await api.createChat(adminToken, {
      name: newChatName,
      user_ids: [user2Session.user_id.id],
    });

    // user2 видит новый чат в списке без перезагрузки
    await user2Chat.expectChatInList(newChatName);

    await api.deleteChat(adminToken, newChat.id);
  });
});
