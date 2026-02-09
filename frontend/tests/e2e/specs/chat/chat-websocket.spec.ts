import { test, expect } from '../../fixtures';
import { ChatPage } from '../../pages/ChatPage';
import { WSClient } from '../../helpers/ws.helper';

/**
 * WebSocket тесты — real-time события между двумя пользователями.
 *
 * Архитектура:
 *   - adminWS / user2WS — Node.js WS клиенты (helpers/ws.helper.ts)
 *   - page / user2Page — браузерные страницы (Playwright)
 *   - api — прямые HTTP вызовы для setup данных
 *
 * Паттерн: один пользователь делает действие → другой получает WS событие.
 */
test.describe('WebSocket — подключение и heartbeat', () => {
  test('подключение и получение pong на ping', async ({ adminWS }) => {
    adminWS.send({ type: 'ping' });
    const pong = await adminWS.waitFor(
      (msg) => msg.type === 'pong',
      5_000,
    );
    expect(pong.type).toBe('pong');
  });

  test('подписка на чат через WS', async ({ adminWS, api, adminToken }) => {
    const chat = await api.createChat(adminToken, { name: 'WS Sub Test' });
    const result = await adminWS.subscribe(chat.id);
    expect(result.type).toBe('subscribed');
    expect(result.chat_id).toBe(chat.id);
    await api.deleteChat(adminToken, chat.id);
  });

  test('subscribe_all на несколько чатов', async ({ adminWS, api, adminToken }) => {
    const chat1 = await api.createChat(adminToken, { name: 'WS Multi 1' });
    const chat2 = await api.createChat(adminToken, { name: 'WS Multi 2' });

    const result = await adminWS.subscribeAll([chat1.id, chat2.id]);
    expect(result.type).toBe('subscribed_all');
    expect(result.count).toBe(2);

    await api.deleteChat(adminToken, chat1.id);
    await api.deleteChat(adminToken, chat2.id);
  });
});

test.describe('WebSocket — new_message между двумя пользователями', () => {
  let chatId: number;

  test.beforeEach(async ({ api, adminToken, user2Session }) => {
    const chat = await api.createChat(adminToken, {
      name: `WS Msg ${Date.now()}`,
      user_ids: [user2Session.user_id.id],
    });
    chatId = chat.id;
  });

  test.afterEach(async ({ api, adminToken }) => {
    await api.deleteChat(adminToken, chatId).catch(() => {});
  });

  test('user2 получает new_message когда admin отправляет сообщение через API', async ({
    adminToken,
    user2WS,
    api,
  }) => {
    // user2 подписывается на чат
    await user2WS.subscribe(chatId);
    user2WS.clearMessages();

    // admin отправляет сообщение
    await api.sendMessage(adminToken, chatId, 'Привет от admin!');

    // user2 получает событие
    const event = await user2WS.waitForNewMessage(chatId);
    expect(event.type).toBe('new_message');
    expect(event.chat_id).toBe(chatId);
    expect(event.message.body).toBe('Привет от admin!');
  });

  test('admin получает new_message когда user2 отправляет через API', async ({
    adminWS,
    user2Token,
    api,
  }) => {
    await adminWS.subscribe(chatId);
    adminWS.clearMessages();

    await api.sendMessage(user2Token, chatId, 'Привет от user2!');

    const event = await adminWS.waitForNewMessage(chatId);
    expect(event.message.body).toBe('Привет от user2!');
  });

  test('отправитель НЕ получает своё сообщение обратно по WS', async ({
    adminWS,
    adminToken,
    api,
  }) => {
    await adminWS.subscribe(chatId);
    adminWS.clearMessages();

    await api.sendMessage(adminToken, chatId, 'Моё сообщение');

    // Не должны получить new_message для своего сообщения
    // (exclude_user в send_to_chat)
    await adminWS.expectNoEvent(
      (msg) =>
        msg.type === 'new_message' &&
        msg.chat_id === chatId &&
        msg.message?.body === 'Моё сообщение',
      3_000,
    );
  });

  test('несколько сообщений приходят в правильном порядке', async ({
    adminToken,
    user2WS,
    api,
  }) => {
    await user2WS.subscribe(chatId);
    user2WS.clearMessages();

    await api.sendMessage(adminToken, chatId, 'Сообщение 1');
    await api.sendMessage(adminToken, chatId, 'Сообщение 2');
    await api.sendMessage(adminToken, chatId, 'Сообщение 3');

    // Ждём все 3
    await user2WS.waitFor(
      (msg) => msg.type === 'new_message' && msg.message?.body === 'Сообщение 3',
    );

    const newMessages = user2WS
      .getMessages()
      .filter((m) => m.type === 'new_message' && m.chat_id === chatId);

    expect(newMessages).toHaveLength(3);
    expect(newMessages[0].message.body).toBe('Сообщение 1');
    expect(newMessages[1].message.body).toBe('Сообщение 2');
    expect(newMessages[2].message.body).toBe('Сообщение 3');
  });
});

test.describe('WebSocket — typing indicator', () => {
  let chatId: number;

  test.beforeEach(async ({ api, adminToken, user2Session }) => {
    const chat = await api.createChat(adminToken, {
      name: `WS Typing ${Date.now()}`,
      user_ids: [user2Session.user_id.id],
    });
    chatId = chat.id;
  });

  test.afterEach(async ({ api, adminToken }) => {
    await api.deleteChat(adminToken, chatId).catch(() => {});
  });

  test('user2 получает typing от admin', async ({
    adminWS,
    user2WS,
    adminSession,
  }) => {
    await adminWS.subscribe(chatId);
    await user2WS.subscribe(chatId);
    user2WS.clearMessages();

    adminWS.sendTyping(chatId);

    const event = await user2WS.waitForTyping(chatId);
    expect(event.type).toBe('typing');
    expect(event.user_id).toBe(adminSession.user_id.id);
  });

  test('отправитель typing НЕ получает свой typing', async ({
    adminWS,
  }) => {
    await adminWS.subscribe(chatId);
    adminWS.clearMessages();

    adminWS.sendTyping(chatId);

    await adminWS.expectNoEvent(
      (msg) => msg.type === 'typing' && msg.chat_id === chatId,
      2_000,
    );
  });
});

test.describe('WebSocket — message_edited и message_deleted', () => {
  let chatId: number;

  test.beforeEach(async ({ api, adminToken, user2Session }) => {
    const chat = await api.createChat(adminToken, {
      name: `WS Edit ${Date.now()}`,
      user_ids: [user2Session.user_id.id],
    });
    chatId = chat.id;
  });

  test.afterEach(async ({ api, adminToken }) => {
    await api.deleteChat(adminToken, chatId).catch(() => {});
  });

  test('user2 получает message_edited при редактировании', async ({
    adminToken,
    user2WS,
    api,
  }) => {
    await user2WS.subscribe(chatId);

    // Создаём сообщение
    const { data: msg } = await api.sendMessage(
      adminToken,
      chatId,
      'Оригинал',
    );
    user2WS.clearMessages();

    // Редактируем через API
    const res = await fetch(
      `${process.env.API_URL || 'http://localhost:8090'}/chats/${chatId}/messages/${msg.id}`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${adminToken}`,
        },
        body: JSON.stringify({ body: 'Отредактировано' }),
      },
    );
    expect(res.ok).toBeTruthy();

    const event = await user2WS.waitForMessageEdited(chatId, msg.id);
    expect(event.type).toBe('message_edited');
    expect(event.body).toBe('Отредактировано');
  });

  test('user2 получает message_deleted при удалении', async ({
    adminToken,
    user2WS,
    api,
  }) => {
    await user2WS.subscribe(chatId);

    const { data: msg } = await api.sendMessage(
      adminToken,
      chatId,
      'Удали меня',
    );
    user2WS.clearMessages();

    // Удаляем через API
    const res = await fetch(
      `${process.env.API_URL || 'http://localhost:8090'}/chats/${chatId}/messages/${msg.id}`,
      {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${adminToken}` },
      },
    );
    expect(res.ok).toBeTruthy();

    const event = await user2WS.waitForMessageDeleted(chatId);
    expect(event.type).toBe('message_deleted');
    expect(event.message_id).toBe(msg.id);
  });
});

test.describe('WebSocket — messages_read', () => {
  let chatId: number;

  test.beforeEach(async ({ api, adminToken, user2Session }) => {
    const chat = await api.createChat(adminToken, {
      name: `WS Read ${Date.now()}`,
      user_ids: [user2Session.user_id.id],
    });
    chatId = chat.id;
  });

  test.afterEach(async ({ api, adminToken }) => {
    await api.deleteChat(adminToken, chatId).catch(() => {});
  });

  test('admin получает messages_read когда user2 читает', async ({
    adminWS,
    user2WS,
    user2Token,
    user2Session,
    api,
  }) => {
    await adminWS.subscribe(chatId);
    await user2WS.subscribe(chatId);

    // admin отправляет сообщение
    await api.sendMessage(adminToken, chatId, 'Прочитай это');
    adminWS.clearMessages();

    // user2 отмечает прочитанным через WS
    user2WS.sendRead(chatId);

    // admin получает messages_read
    const event = await adminWS.waitForMessagesRead(chatId);
    expect(event.type).toBe('messages_read');
    expect(event.chat_id).toBe(chatId);
    expect(event.user_id).toBe(user2Session.user_id.id);
  });
});

test.describe('WebSocket — presence (online/offline)', () => {
  // Presence тесты создают свои WS подключения чтобы не конфликтовать с fixtures
  const WS_URL_LOCAL = (process.env.API_URL || 'http://localhost:8090').replace('http', 'ws');

  test('presence:online приходит при подключении пользователя', async ({
    adminToken,
    user2Token,
    adminSession,
  }) => {
    // Подключаем user2 первым
    const user2ws = new WSClient(WS_URL_LOCAL, user2Token);
    await user2ws.connect();
    user2ws.clearMessages();

    // Подключаем admin — user2 должен получить presence:online
    const adminws = new WSClient(WS_URL_LOCAL, adminToken);
    await adminws.connect();

    const event = await user2ws.waitForPresence(
      adminSession.user_id.id,
      'online',
    );
    expect(event.type).toBe('presence');
    expect(event.status).toBe('online');

    await adminws.close();
    await user2ws.close();
  });

  test('presence:offline приходит при отключении пользователя', async ({
    adminToken,
    user2Token,
    adminSession,
  }) => {
    const user2ws = new WSClient(WS_URL_LOCAL, user2Token);
    await user2ws.connect();

    const adminws = new WSClient(WS_URL_LOCAL, adminToken);
    await adminws.connect();

    // Ждём online сначала
    await user2ws.waitForPresence(adminSession.user_id.id, 'online');
    user2ws.clearMessages();

    // Отключаем admin
    await adminws.close();

    const event = await user2ws.waitForPresence(
      adminSession.user_id.id,
      'offline',
      10_000,
    );
    expect(event.type).toBe('presence');
    expect(event.status).toBe('offline');

    await user2ws.close();
  });
});

test.describe('WebSocket — chat_created (новый чат в реальном времени)', () => {
  test('user2 получает chat_created при добавлении в чат', async ({
    user2WS,
    adminToken,
    user2Session,
    api,
  }) => {
    user2WS.clearMessages();

    // admin создаёт чат с user2
    const chatName = `Realtime Chat ${Date.now()}`;
    const chat = await api.createChat(adminToken, {
      name: chatName,
      user_ids: [user2Session.user_id.id],
    });

    const event = await user2WS.waitForChatCreated();
    expect(event.type).toBe('chat_created');
    expect(event.chat_id).toBe(chat.id);

    await api.deleteChat(adminToken, chat.id);
  });
});

test.describe('WebSocket — изоляция подписок', () => {
  test('user2 НЕ получает сообщения из чата, на который не подписан', async ({
    adminWS,
    user2WS,
    adminToken,
    api,
  }) => {
    // Чат без user2
    const chat = await api.createChat(adminToken, {
      name: `Isolated ${Date.now()}`,
    });

    await adminWS.subscribe(chat.id);
    // user2 НЕ подписывается

    user2WS.clearMessages();

    await api.sendMessage(adminToken, chat.id, 'Секретное сообщение');

    // user2 не должен получить событие
    await user2WS.expectNoEvent(
      (msg) => msg.type === 'new_message' && msg.chat_id === chat.id,
      3_000,
    );

    await api.deleteChat(adminToken, chat.id);
  });

  test('после unsubscribe сообщения не приходят', async ({
    adminWS,
    user2WS,
    adminToken,
    user2Session,
    api,
  }) => {
    const chat = await api.createChat(adminToken, {
      name: `Unsub Test ${Date.now()}`,
      user_ids: [user2Session.user_id.id],
    });

    await user2WS.subscribe(chat.id);

    // Отписываемся
    user2WS.send({ type: 'unsubscribe', chat_id: chat.id });
    await user2WS.waitFor((msg) => msg.type === 'unsubscribed');

    user2WS.clearMessages();

    await api.sendMessage(adminToken, chat.id, 'После отписки');

    await user2WS.expectNoEvent(
      (msg) => msg.type === 'new_message' && msg.chat_id === chat.id,
      3_000,
    );

    await api.deleteChat(adminToken, chat.id);
  });
});
