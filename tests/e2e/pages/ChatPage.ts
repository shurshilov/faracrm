import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object для страницы чата.
 *
 * Структура UI:
 * - Sidebar (ChatSidebar): навигация ВНУТРЕННИЕ (Все/Личные/Группы) + ВНЕШНИЕ
 * - Main: ChatPage = ChatList (список чатов) + ChatMessages (сообщения)
 *
 * URL: /chat?is_internal=true — все внутренние чаты
 * Для загрузки ChatList нужно кликнуть категорию в sidebar.
 */
export class ChatPage {
  readonly newChatButton: Locator;
  readonly messageInput: Locator;
  readonly sendButton: Locator;
  readonly messagesContainer: Locator;

  constructor(private page: Page) {
    this.newChatButton = page.locator('[title="Новый чат"], [title="New chat"]').first();
    this.messageInput = page.locator(
      'textarea[class*="ChatInput"], [class*="chatInput"] textarea, [contenteditable]',
    ).first();
    this.sendButton = page.locator(
      'button[class*="send"], [class*="ChatInput"] button[type="submit"]',
    ).last();
    this.messagesContainer = page.locator(
      '[class*="ChatMessages"], [class*="messages"]',
    ).first();
  }

  /**
   * Перейти на страницу чатов и загрузить список внутренних чатов.
   * Кликает "Все" в sidebar ВНУТРЕННИЕ для загрузки ChatList.
   */
  async goto() {
    // Переходим на /chat
    await this.page.goto('/chat');
    await this.page.waitForLoadState('networkidle');

    // Ждём появления sidebar
    await this.page.waitForTimeout(1000);

    // Кликаем первую кнопку "Все" (ВНУТРЕННИЕ → Все)
    await this._clickAllInternal();

    // Ждём загрузки ChatList — input поиска или список чатов
    await this._waitForChatList();
  }

  /** Кликнуть "Все" в секции ВНУТРЕННИЕ sidebar */
  private async _clickAllInternal() {
    // Первая кнопка "Все" — это "Все" в секции ВНУТРЕННИЕ
    const allBtn = this.page.locator('button:has-text("Все")').first();
    await allBtn.waitFor({ state: 'visible', timeout: 10_000 });
    await allBtn.click();
    await this.page.waitForTimeout(1500);
  }

  /** Дождаться что ChatList загрузился */
  private async _waitForChatList() {
    // ChatList рендерит поле поиска или текст "Нет чатов"
    const chatListIndicator = this.page.locator(
      '[class*="chatList"], [class*="ChatList"], [placeholder*="поиск" i], [placeholder*="search" i]',
    ).first();

    try {
      await chatListIndicator.waitFor({ state: 'visible', timeout: 10_000 });
    } catch {
      // ChatList мог не загрузиться — попробуем ещё раз кликнуть "Все"
      await this._clickAllInternal();
    }
  }

  // ==================== Навигация ====================

  /** Открыть чат по имени. При необходимости reload. */
  async openChat(chatName: string) {
    const chatItem = this.page.getByText(chatName, { exact: false }).first();

    let visible = await chatItem.isVisible().catch(() => false);

    if (!visible) {
      // Reload — API вернёт свежие данные
      await this.page.reload({ waitUntil: 'networkidle' });
      await this._clickAllInternal();
      await this._waitForChatList();
      visible = await chatItem.isVisible().catch(() => false);
    }

    if (!visible) {
      // Последняя попытка — полный goto
      await this.goto();
    }

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
    const locator = this.page.getByText(chatName, { exact: false }).first();
    let visible = await locator.isVisible().catch(() => false);
    if (!visible) {
      // Reload и навигация
      await this.page.reload({ waitUntil: 'networkidle' });
      await this._clickAllInternal();
      await this.page.waitForTimeout(2000);
    }
    await expect(locator).toBeVisible({ timeout: 15_000 });
  }

  /** Проверить что чат НЕ виден */
  async expectChatNotInList(chatName: string) {
    await expect(
      this.page.getByText(chatName, { exact: false }),
    ).toHaveCount(0, { timeout: 5_000 });
  }

  // ==================== Создание чата ====================

  async createGroupChat(name: string, memberNames: string[] = []) {
    // newChatButton с title="Новый чат" находится внутри ChatList header
    await this.newChatButton.click();

    const modal = this.page.locator('[class*="Modal"], [role="dialog"]').last();
    await expect(modal).toBeVisible();

    await modal.getByLabel(/название|name/i).fill(name);

    for (const memberName of memberNames) {
      const memberInput = modal.getByPlaceholder(/участник|member|поиск/i);
      if (await memberInput.isVisible()) {
        await memberInput.fill(memberName);
        await this.page.getByText(memberName, { exact: false }).first().click();
      }
    }

    await modal.getByRole('button', { name: /создать|create/i }).click();
    await expect(modal).not.toBeVisible({ timeout: 5_000 });
  }

  // ==================== Сообщения ====================

  async sendMessage(text: string) {
    await this.messageInput.click();
    await this.messageInput.fill(text);
    await this.page.keyboard.press('Enter');
    await expect(
      this.messagesContainer.getByText(text, { exact: false }).first(),
    ).toBeVisible({ timeout: 10_000 });
  }

  get lastMessage(): Locator {
    return this.messagesContainer
      .locator('[class*="message"], [class*="Message"]')
      .last();
  }

  get allMessages(): Locator {
    return this.messagesContainer.locator(
      '[class*="message"], [class*="Message"]',
    );
  }

  async expectMessageVisible(text: string) {
    await expect(
      this.messagesContainer.getByText(text, { exact: false }).first(),
    ).toBeVisible({ timeout: 10_000 });
  }

  async expectMessageNotVisible(text: string) {
    await expect(
      this.messagesContainer.getByText(text, { exact: false }),
    ).toHaveCount(0, { timeout: 5_000 });
  }

  // ==================== Контекстное меню сообщения ====================

  async openMessageActions(messageText: string) {
    const msg = this.messagesContainer
      .getByText(messageText, { exact: false })
      .first();
    await msg.hover();
  }

  async editMessage(originalText: string, newText: string) {
    await this.openMessageActions(originalText);
    await this.page.getByRole('button', { name: /редакт|edit/i }).first().click();
    await this.messageInput.clear();
    await this.messageInput.fill(newText);
    await this.page.keyboard.press('Enter');
    await this.expectMessageVisible(newText);
  }

  async deleteMessage(messageText: string) {
    await this.openMessageActions(messageText);
    await this.page.getByRole('button', { name: /удал|delete/i }).first().click();
    const confirmBtn = this.page.getByRole('button', { name: /да|подтвер|confirm|yes/i });
    if (await confirmBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await confirmBtn.click();
    }
  }

  async addReaction(messageText: string, emoji = '👍') {
    await this.openMessageActions(messageText);
    const reactionBtn = this.page.getByRole('button', {
      name: /реакц|reaction|emoji/i,
    }).first();
    if (await reactionBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await reactionBtn.click();
      await this.page.getByText(emoji).first().click();
    }
  }

  async pinMessage(messageText: string) {
    await this.openMessageActions(messageText);
    await this.page
      .getByRole('button', { name: /закреп|pin/i })
      .first()
      .click();
  }

  // ==================== Typing indicator ====================

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
