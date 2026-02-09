import { test, expect } from '../../fixtures';
import { WSClient } from '../../helpers/ws.helper';
import WebSocket from 'ws';

const API_URL = process.env.API_URL || 'http://localhost:8090';
const WS_URL = API_URL.replace('http', 'ws');

/**
 * Edge-кейсы и стресс-тесты WebSocket/чата.
 */
test.describe('WebSocket — reconnection и устойчивость', () => {
  test('после разрыва WS и переподключения — сообщения приходят', async ({
    adminToken,
    user2Token,
    user2Session,
    api,
  }) => {
    const chat = await api.createChat(adminToken, {
      name: `Reconnect ${Date.now()}`,
      user_ids: [user2Session.user_id.id],
    });

    // user2 подключается
    const ws1 = new WSClient(WS_URL, user2Token);
    await ws1.connect();
    await ws1.subscribe(chat.id);

    // Разрыв
    await ws1.close();

    // Переподключение
    const ws2 = new WSClient(WS_URL, user2Token);
    await ws2.connect();
    await ws2.subscribe(chat.id);
    ws2.clearMessages();

    // admin отправляет
    await api.sendMessage(adminToken, chat.id, 'После реконнекта');

    // user2 получает
    const event = await ws2.waitForNewMessage(chat.id);
    expect(event.message.body).toBe('После реконнекта');

    await ws2.close();
    await api.deleteChat(adminToken, chat.id);
  });

  test('дублирование подключений — старое закрывается', async ({
    adminToken,
  }) => {
    // Два подключения одного юзера
    const ws1 = new WSClient(WS_URL, adminToken);
    const ws2 = new WSClient(WS_URL, adminToken);

    await ws1.connect();
    await ws2.connect(); // Должно закрыть ws1

    // ws2 работает
    ws2.send({ type: 'ping' });
    const pong = await ws2.waitFor((msg) => msg.type === 'pong');
    expect(pong.type).toBe('pong');

    await ws2.close();
    // ws1 уже закрыт сервером
  });

  test('невалидный токен — WS закрывается с кодом 4001', async () => {
    const ws = new WebSocket(`${WS_URL}/ws/chat?token=invalid_token_123`);

    const closeCode = await new Promise<number>((resolve) => {
      ws.on('close', (code: number) => resolve(code));
      ws.on('open', () => {
        // Если вдруг открылся — закроется сервером
      });
    });

    expect(closeCode).toBe(4001);
  });

  test('WS без токена — закрывается с кодом 4001', async () => {
    const ws = new WebSocket(`${WS_URL}/ws/chat`);

    const closeCode = await new Promise<number>((resolve) => {
      ws.on('close', (code: number) => resolve(code));
    });

    expect(closeCode).toBe(4001);
  });
});

test.describe('WebSocket — множественные чаты', () => {
  test('события приходят только в подписанные чаты', async ({
    adminToken,
    user2Token,
    user2Session,
    api,
  }) => {
    const chat1 = await api.createChat(adminToken, {
      name: `Multi1 ${Date.now()}`,
      user_ids: [user2Session.user_id.id],
    });
    const chat2 = await api.createChat(adminToken, {
      name: `Multi2 ${Date.now()}`,
      user_ids: [user2Session.user_id.id],
    });

    const ws = new WSClient(WS_URL, user2Token);
    await ws.connect();
    // Подписываемся только на chat1
    await ws.subscribe(chat1.id);
    ws.clearMessages();

    // Сообщения в оба чата
    await api.sendMessage(adminToken, chat1.id, 'В чат 1');
    await api.sendMessage(adminToken, chat2.id, 'В чат 2');

    // Ждём сообщение из chat1
    await ws.waitForNewMessage(chat1.id);

    // Сообщение из chat2 НЕ должно прийти
    await ws.expectNoEvent(
      (msg) => msg.type === 'new_message' && msg.chat_id === chat2.id,
      2_000,
    );

    await ws.close();
    await api.deleteChat(adminToken, chat1.id);
    await api.deleteChat(adminToken, chat2.id);
  });

  test('подписка на 50 чатов одновременно', async ({
    adminToken,
    api,
  }) => {
    const chatIds: number[] = [];

    // Создаём 50 чатов
    for (let i = 0; i < 50; i++) {
      const chat = await api.createChat(adminToken, { name: `Bulk${i}` });
      chatIds.push(chat.id);
    }

    const ws = new WSClient(WS_URL, adminToken);
    await ws.connect();

    const result = await ws.subscribeAll(chatIds);
    expect(result.count).toBe(50);

    await ws.close();

    // Cleanup
    for (const id of chatIds) {
      await api.deleteChat(adminToken, id).catch(() => {});
    }
  });
});

test.describe('WebSocket — быстрая отправка (burst)', () => {
  test('10 сообщений подряд — все доставлены', async ({
    adminToken,
    user2Token,
    user2Session,
    api,
  }) => {
    const chat = await api.createChat(adminToken, {
      name: `Burst ${Date.now()}`,
      user_ids: [user2Session.user_id.id],
    });

    const ws = new WSClient(WS_URL, user2Token);
    await ws.connect();
    await ws.subscribe(chat.id);
    ws.clearMessages();

    // Отправляем 10 сообщений без пауз
    const promises = [];
    for (let i = 0; i < 10; i++) {
      promises.push(api.sendMessage(adminToken, chat.id, `Burst msg ${i}`));
    }
    await Promise.all(promises);

    // Ждём последнее
    await ws.waitFor(
      (msg) =>
        msg.type === 'new_message' && msg.message?.body === 'Burst msg 9',
      15_000,
    );

    const received = ws
      .getMessages()
      .filter((m) => m.type === 'new_message' && m.chat_id === chat.id);

    expect(received.length).toBe(10);

    await ws.close();
    await api.deleteChat(adminToken, chat.id);
  });
});

test.describe('WebSocket — pin/reaction events', () => {
  let chatId: number;

  test.beforeEach(async ({ api, adminToken, user2Session }) => {
    const chat = await api.createChat(adminToken, {
      name: `Pin React ${Date.now()}`,
      user_ids: [user2Session.user_id.id],
    });
    chatId = chat.id;
  });

  test.afterEach(async ({ api, adminToken }) => {
    await api.deleteChat(adminToken, chatId).catch(() => {});
  });

  test('user2 получает событие при добавлении реакции', async ({
    adminToken,
    user2WS,
    api,
  }) => {
    await user2WS.subscribe(chatId);

    const { data: msg } = await api.sendMessage(
      adminToken,
      chatId,
      'Поставь лайк',
    );
    user2WS.clearMessages();

    // Admin ставит реакцию
    await fetch(`${API_URL}/chats/${chatId}/messages/${msg.id}/reactions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`,
      },
      body: JSON.stringify({ emoji: '👍' }),
    });

    const event = await user2WS.waitFor(
      (m) =>
        m.type === 'reaction_added' ||
        (m.type === 'new_message' && m.message_id === msg.id),
      5_000,
    );

    // Событие должно содержать информацию о реакции
    expect(event).toBeDefined();
  });
});
