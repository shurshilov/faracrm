import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object для страницы чата (/chats).
 * Покрывает: список чатов, создание чата, отправку/редактирование/удаление сообщений,
 * реакции, пин, пересылку, набор текста.
 */
export class ChatPage {
  // --- Sidebar (список чатов) ---
  readonly chatList: Locator;
  readonly newChatButton: Locator;
  readonly searchChatsInput: Locator;

  // --- Messages area ---
  readonly messageInput: Locator;
  readonly sendButton: Locator;
  readonly messagesContainer: Locator;

  constructor(private page: Page) {
    this.chatList = page.locator('[class*="ChatList"], [class*="chatList"]');
    this.newChatButton = page.getByRole('button', { name: /новый чат|new chat|создать/i });
    this.searchChatsInput = page.getByPlaceholder(/поиск|search/i).first();
    this.messageInput = page.locator(
      'textarea[class*="ChatInput"], [class*="chatInput"] textarea, [contenteditable]',
    ).first();
    this.sendButton = page.locator(
      'button[class*="send"], [class*="ChatInput"] button[type="submit"], [class*="chatInput"] button',
    ).last();
    this.messagesContainer = page.locator(
      '[class*="ChatMessages"], [class*="messages"]',
    ).first();
  }

  async goto() {
    await this.page.goto('/chats');
    // Ждём загрузки списка чатов (API ответ)
    await this.page.waitForResponse(
      (res) => res.url().includes('/chats') && res.ok(),
      { timeout: 15_000 },
    ).catch(() => {});
    await this.page.waitForTimeout(1000);
  }

  // ==================== Навигация ====================

  /** Кликнуть на чат по имени */
  async openChat(chatName: string) {
    // Ждём появления чата в списке (может подгрузиться по WS или при goto)
    const chatItem = this.chatList
      .getByText(chatName, { exact: false })
      .first();
    await chatItem.waitFor({ state: 'visible', timeout: 15_000 });
    await chatItem.click();
    // Ждём загрузки сообщений
    await this.page.waitForResponse(
      (res) => res.url().includes('/messages') && res.ok(),
      { timeout: 10_000 },
    ).catch(() => {});
  }

  /** Проверить что чат виден в списке */
  async expectChatInList(chatName: string) {
    await expect(
      this.chatList.getByText(chatName, { exact: false }).first(),
    ).toBeVisible({ timeout: 10_000 });
  }

  /** Проверить что чат НЕ виден */
  async expectChatNotInList(chatName: string) {
    await expect(
      this.chatList.getByText(chatName, { exact: false }),
    ).toHaveCount(0, { timeout: 5_000 });
  }

  // ==================== Создание чата ====================

  async createGroupChat(name: string, memberNames: string[] = []) {
    await this.newChatButton.click();

    // Модалка создания чата
    const modal = this.page.locator('[class*="Modal"], [role="dialog"]').last();
    await expect(modal).toBeVisible();

    // Вводим имя
    await modal.getByLabel(/название|name/i).fill(name);

    // Добавляем участников
    for (const memberName of memberNames) {
      const memberInput = modal.getByPlaceholder(/участник|member|поиск/i);
      if (await memberInput.isVisible()) {
        await memberInput.fill(memberName);
        await this.page.getByText(memberName, { exact: false }).first().click();
      }
    }

    // Создать
    await modal.getByRole('button', { name: /создать|create/i }).click();
    await expect(modal).not.toBeVisible({ timeout: 5_000 });
  }

  // ==================== Сообщения ====================

  /** Отправить текстовое сообщение */
  async sendMessage(text: string) {
    await this.messageInput.click();
    await this.messageInput.fill(text);
    // Enter или кнопка
    await this.page.keyboard.press('Enter');
    // Ждём появления сообщения в DOM
    await expect(
      this.messagesContainer.getByText(text, { exact: false }).first(),
    ).toBeVisible({ timeout: 10_000 });
  }

  /** Получить последнее сообщение */
  get lastMessage(): Locator {
    return this.messagesContainer
      .locator('[class*="message"], [class*="Message"]')
      .last();
  }

  /** Получить все сообщения */
  get allMessages(): Locator {
    return this.messagesContainer.locator(
      '[class*="message"], [class*="Message"]',
    );
  }

  /** Проверить что сообщение с текстом видимо */
  async expectMessageVisible(text: string) {
    await expect(
      this.messagesContainer.getByText(text, { exact: false }).first(),
    ).toBeVisible({ timeout: 10_000 });
  }

  /** Проверить что сообщение удалено (не видимо или помечено) */
  async expectMessageNotVisible(text: string) {
    await expect(
      this.messagesContainer.getByText(text, { exact: false }),
    ).toHaveCount(0, { timeout: 5_000 });
  }

  // ==================== Контекстное меню сообщения ====================

  /** Правый клик / hover на сообщение для открытия действий */
  async openMessageActions(messageText: string) {
    const msg = this.messagesContainer
      .getByText(messageText, { exact: false })
      .first();
    // Hover для отображения action buttons
    await msg.hover();
    // Или правый клик если контекстное меню
    // await msg.click({ button: 'right' });
  }

  /** Редактировать сообщение */
  async editMessage(originalText: string, newText: string) {
    await this.openMessageActions(originalText);
    // Клик на кнопку редактирования
    await this.page.getByRole('button', { name: /редакт|edit/i }).first().click();
    // Очищаем и вводим новый текст
    await this.messageInput.clear();
    await this.messageInput.fill(newText);
    await this.page.keyboard.press('Enter');
    await this.expectMessageVisible(newText);
  }

  /** Удалить сообщение */
  async deleteMessage(messageText: string) {
    await this.openMessageActions(messageText);
    await this.page.getByRole('button', { name: /удал|delete/i }).first().click();
    // Подтверждение если есть
    const confirmBtn = this.page.getByRole('button', { name: /да|подтвер|confirm|yes/i });
    if (await confirmBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await confirmBtn.click();
    }
  }

  /** Добавить реакцию */
  async addReaction(messageText: string, emoji = '👍') {
    await this.openMessageActions(messageText);
    // Кнопка реакции
    const reactionBtn = this.page.getByRole('button', {
      name: /реакц|reaction|emoji/i,
    }).first();
    if (await reactionBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await reactionBtn.click();
      await this.page.getByText(emoji).first().click();
    }
  }

  /** Закрепить сообщение */
  async pinMessage(messageText: string) {
    await this.openMessageActions(messageText);
    await this.page
      .getByRole('button', { name: /закреп|pin/i })
      .first()
      .click();
  }

  // ==================== Typing indicator ====================

  /** Проверить что индикатор набора виден */
  async expectTypingIndicator(userName?: string) {
    const typingLocator = userName
      ? this.page.getByText(new RegExp(`${userName}.*набира|${userName}.*typing`, 'i'))
      : this.page.locator('[class*="typing"], [class*="Typing"]');
    await expect(typingLocator.first()).toBeVisible({ timeout: 5_000 });
  }

  // ==================== Scroll ====================

  async scrollToTop() {
    await this.messagesContainer.evaluate((el) => (el.scrollTop = 0));
  }

  async scrollToBottom() {
    await this.messagesContainer.evaluate(
      (el) => (el.scrollTop = el.scrollHeight),
    );
  }
}
