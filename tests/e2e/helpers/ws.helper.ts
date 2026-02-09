/**
 * WebSocket helper — подключение к WS из тестов для проверки событий.
 *
 * В отличие от браузерного WS, этот клиент работает в Node.js
 * и позволяет: подключаться несколькими юзерами, ждать конкретные события,
 * проверять порядок и содержимое.
 */
import WebSocket from 'ws';

export interface WSEvent {
  type: string;
  [key: string]: any;
}

export class WSClient {
  private ws: WebSocket | null = null;
  private messages: WSEvent[] = [];
  private isReady = false;
  private waiters: Array<{
    predicate: (msg: WSEvent) => boolean;
    resolve: (msg: WSEvent) => void;
    reject: (err: Error) => void;
    timer: NodeJS.Timeout;
  }> = [];

  constructor(
    private wsUrl: string,
    private token: string,
  ) {}

  /** Подключиться и дождаться открытия + connected event */
  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const url = `${this.wsUrl}/ws/chat?token=${this.token}`;
      this.ws = new WebSocket(url);

      const timeout = setTimeout(() => reject(new Error('WS connect timeout')), 10_000);

      this.ws.on('error', (err) => {
        clearTimeout(timeout);
        reject(err);
      });

      this.ws.on('message', (raw: WebSocket.Data) => {
        try {
          const msg: WSEvent = JSON.parse(raw.toString());
          this.messages.push(msg);

          // Первое сообщение connected = подключение готово
          if (msg.type === 'connected' && !this.isReady) {
            this.isReady = true;
            clearTimeout(timeout);
            resolve();
          }

          // Проверяем ожидающих
          for (let i = this.waiters.length - 1; i >= 0; i--) {
            const waiter = this.waiters[i];
            if (waiter.predicate(msg)) {
              clearTimeout(waiter.timer);
              waiter.resolve(msg);
              this.waiters.splice(i, 1);
            }
          }
        } catch {
          // non-JSON, ignore
        }
      });

      this.ws.on('close', () => {
        // Reject all pending waiters
        for (const waiter of this.waiters) {
          clearTimeout(waiter.timer);
          waiter.reject(new Error('WebSocket closed while waiting'));
        }
        this.waiters = [];
      });
    });
  }

  /** Отправить сообщение */
  send(data: Record<string, any>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected');
    }
    this.ws.send(JSON.stringify(data));
  }

  /** Подписаться на чат */
  async subscribe(chatId: number): Promise<WSEvent> {
    this.send({ type: 'subscribe', chat_id: chatId });
    return this.waitFor((msg) => msg.type === 'subscribed' && msg.chat_id === chatId);
  }

  /** Подписаться на несколько чатов */
  async subscribeAll(chatIds: number[]): Promise<WSEvent> {
    this.send({ type: 'subscribe_all', chat_ids: chatIds });
    return this.waitFor((msg) => msg.type === 'subscribed_all');
  }

  /** Отправить typing */
  sendTyping(chatId: number): void {
    this.send({ type: 'typing', chat_id: chatId });
  }

  /** Отправить read */
  sendRead(chatId: number, messageId?: number): void {
    this.send({ type: 'read', chat_id: chatId, message_id: messageId });
  }

  /** Ждать конкретное событие по предикату */
  async waitFor(
    predicate: (msg: WSEvent) => boolean,
    timeoutMs = 10_000,
  ): Promise<WSEvent> {
    // Проверяем уже пришедшие
    const existing = this.messages.find(predicate);
    if (existing) return existing;

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        const idx = this.waiters.findIndex((w) => w.resolve === resolve);
        if (idx >= 0) this.waiters.splice(idx, 1);
        reject(
          new Error(
            `Timeout waiting for WS event. Received: ${JSON.stringify(this.messages.map((m) => m.type))}`,
          ),
        );
      }, timeoutMs);

      this.waiters.push({ predicate, resolve, reject, timer });
    });
  }

  /** Ждать new_message в конкретном чате */
  async waitForNewMessage(chatId: number, timeoutMs = 10_000): Promise<WSEvent> {
    return this.waitFor(
      (msg) => msg.type === 'new_message' && msg.chat_id === chatId,
      timeoutMs,
    );
  }

  /** Ждать message_edited */
  async waitForMessageEdited(chatId: number, messageId?: number, timeoutMs = 10_000): Promise<WSEvent> {
    return this.waitFor(
      (msg) =>
        msg.type === 'message_edited' &&
        msg.chat_id === chatId &&
        (messageId ? msg.message_id === messageId : true),
      timeoutMs,
    );
  }

  /** Ждать message_deleted */
  async waitForMessageDeleted(chatId: number, timeoutMs = 10_000): Promise<WSEvent> {
    return this.waitFor(
      (msg) => msg.type === 'message_deleted' && msg.chat_id === chatId,
      timeoutMs,
    );
  }

  /** Ждать typing */
  async waitForTyping(chatId: number, timeoutMs = 5_000): Promise<WSEvent> {
    return this.waitFor(
      (msg) => msg.type === 'typing' && msg.chat_id === chatId,
      timeoutMs,
    );
  }

  /** Ждать presence (online/offline) */
  async waitForPresence(userId: number, status?: string, timeoutMs = 10_000): Promise<WSEvent> {
    return this.waitFor(
      (msg) =>
        msg.type === 'presence' &&
        msg.user_id === userId &&
        (status ? msg.status === status : true),
      timeoutMs,
    );
  }

  /** Ждать messages_read */
  async waitForMessagesRead(chatId: number, timeoutMs = 10_000): Promise<WSEvent> {
    return this.waitFor(
      (msg) => msg.type === 'messages_read' && msg.chat_id === chatId,
      timeoutMs,
    );
  }

  /** Ждать chat_created */
  async waitForChatCreated(timeoutMs = 10_000): Promise<WSEvent> {
    return this.waitFor((msg) => msg.type === 'chat_created', timeoutMs);
  }

  /** Убедиться что событие НЕ приходит (negative test) */
  async expectNoEvent(
    predicate: (msg: WSEvent) => boolean,
    waitMs = 3_000,
  ): Promise<void> {
    try {
      await this.waitFor(predicate, waitMs);
      throw new Error('Expected no event but received one');
    } catch (err: any) {
      if (err.message.includes('Timeout')) return; // Ожидаемый таймаут
      throw err;
    }
  }

  /** Получить все накопленные сообщения */
  getMessages(): WSEvent[] {
    return [...this.messages];
  }

  /** Очистить накопленные сообщения */
  clearMessages(): void {
    this.messages = [];
  }

  /** Закрыть соединение */
  async close(): Promise<void> {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
