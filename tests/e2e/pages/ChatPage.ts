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
    this.messageInput = page.getByPlaceholder(/введите сообщение|type.*message/i).first();
    this.sendButton = page.locator(
      'button[class*="send"], [class*="ChatInput"] button[type="submit"]',
    ).last();
    // Ограничиваем messagesContainer правой частью (chatArea) — 
    // исключаем sidebar со списком чатов, где отображается last_message preview
    this.messagesContainer = page.locator('[class*="chatArea"], [class*="chat-area"]').first();
  }

  /**
   * Перейти на страницу чатов и загрузить список внутренних чатов.
   * Кликает "Все" в sidebar ВНУТРЕННИЕ для загрузки ChatList.
   */
  async goto() {
    // Переходим на /chat
    await this.page.goto('/chat');
    await this.page.waitForLoadState('networkidle');

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
    // Ждём реакцию UI — список чатов или поле поиска
    await this.page.locator(
      '[class*="chatList"], [class*="ChatList"], [placeholder*="поиск" i], [placeholder*="search" i]',
    ).first().waitFor({ state: 'visible', timeout: 5_000 }).catch(() => {});
  }

  /** Дождаться что ChatList загрузился */
  private async _waitForChatList() {
    // ChatList рендерит поле поиска или текст "Нет чатов"
    const chatListIndicator = this.page.locator(
      '[class*="chatList"], [class*="ChatList"], [placeholder*="поиск" i], [placeholder*="search" i]',
    ).first();

    try {
      await chatListIndicator.waitFor({ state: 'visible', timeout: 5_000 });
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

    // Ждём загрузки области сообщений — поле ввода доступно
    await this.messageInput.waitFor({ state: 'visible', timeout: 10_000 });
  }

  /** Проверить что чат виден в списке */
  async expectChatInList(chatName: string) {
    const locator = this.page.getByText(chatName, { exact: false }).first();
    let visible = await locator.isVisible().catch(() => false);
    if (!visible) {
      // Reload и навигация
      await this.page.reload({ waitUntil: 'networkidle' });
      await this._clickAllInternal();
    }
    await expect(locator).toBeVisible({ timeout: 15_000 });
  }

  /** Проверить что чат НЕ виден */
  async expectChatNotInList(chatName: string) {
    await expect(
      this.page.getByText(chatName, { exact: false }),
    ).toHaveCount(0, { timeout: 5_000 });
  }

  /** Проверить что у чата есть бейдж непрочитанных сообщений */
  async expectUnreadBadge(chatName: string) {
    // Находим элемент чата в списке
    const chatItem = this.page.locator('[class*="chatItem"], [class*="ChatItem"], [class*="chat-item"]')
      .filter({ hasText: chatName }).first();
    // Если не нашли по классу — ищем по тексту рядом с бейджем
    const badge = chatItem.locator('[class*="badge"], [class*="Badge"], [class*="unread"]').first();
    await expect(badge).toBeVisible({ timeout: 10_000 });
  }

  // ==================== Создание чата ====================

  async createGroupChat(name: string, memberNames: string[] = []) {
    await this.newChatButton.click();

    // Ждём появления модалки
    await expect(this.page.getByText('Новый чат').first()).toBeVisible({ timeout: 5_000 });

    // Переключаемся на таб "Группа"
    await this.page.getByText(/^Группа$/i).first().click();

    // Вводим название группы
    const nameInput = this.page.getByPlaceholder(/введите название группы|enter.*group.*name/i).first();
    if (await nameInput.isVisible().catch(() => false)) {
      await nameInput.fill(name);
    } else {
      await this.page.getByLabel(/название группы|group.*name/i).first().fill(name);
    }

    // Добавляем участников через MultiSelect
    if (memberNames.length > 0) {
      const memberInput = this.page.getByPlaceholder(/поиск.*пользовател|search.*user/i).first();
      for (const memberName of memberNames) {
        await memberInput.click();
        await memberInput.fill(memberName);
        // Ждём dropdown
        await this.page.getByRole('option').first().waitFor({ state: 'visible', timeout: 3_000 }).catch(() => {});
        // Кликаем по опции в dropdown
        await this.page.getByRole('option', { name: new RegExp(memberName, 'i') }).first().click().catch(async () => {
          // Fallback: ищем текст в dropdown
          await this.page.locator('[class*="option"], [role="listbox"] [role="option"]')
            .filter({ hasText: memberName })
            .first()
            .click();
        });
      }
    }

    // Создать — сначала закрываем dropdown участников (кликаем вне него)
    await this.page.keyboard.press('Escape');
    await this.page.getByRole('button', { name: /^создать$|^create$/i }).click();
    // Ждём закрытия модалки
    await expect(this.page.getByText('Новый чат').first()).toBeHidden({ timeout: 5_000 }).catch(() => {});
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
    ).toBeVisible({ timeout: 15_000 });
  }

  async expectMessageNotVisible(text: string) {
    await expect(
      this.messagesContainer.getByText(text, { exact: false }),
    ).toHaveCount(0, { timeout: 10_000 });
  }

  // ==================== Контекстное меню сообщения ====================

  /**
   * Открыть контекстное меню сообщения (правый клик).
   * UI использует onContextMenu → custom Paper popup,
   * а не hover-кнопки с role="button".
   */
  async openMessageActions(messageText: string) {
    const msg = this.messagesContainer
      .getByText(messageText, { exact: false })
      .first();
    await msg.click({ button: 'right' });
    // Ждём появления контекстного меню
    await this.page.locator('[class*="contextMenu"]').first().waitFor({ state: 'visible', timeout: 3_000 });
  }

  async editMessage(originalText: string, newText: string) {
    await this.openMessageActions(originalText);
    // Контекстное меню — это Box элементы с Text внутри, не button
    await this.page.locator('[class*="contextMenuItem"]').filter({ hasText: /редактировать|edit/i }).first().click();
    // Редактирование открывает Modal с TextInput
    const editInput = this.page.locator('input[placeholder], .mantine-TextInput-input').last();
    await editInput.waitFor({ state: 'visible', timeout: 5_000 });
    await editInput.clear();
    await editInput.fill(newText);
    // Кликаем "Сохранить" в модалке
    await this.page.getByRole('button', { name: /сохранить|save/i }).click();
    // Ждём закрытия модалки вместо фиксированного timeout
    await expect(this.page.getByRole('button', { name: /сохранить|save/i })).toBeHidden({ timeout: 5_000 }).catch(() => {});
    await this.expectMessageVisible(newText);
  }

  async deleteMessage(messageText: string) {
    await this.openMessageActions(messageText);
    // Контекстное меню — Box с className contextMenuItemDanger для удаления
    await this.page.locator('[class*="contextMenuItem"]').filter({ hasText: /удалить|delete/i }).first().click();
    // Опционально: подтверждение
    const confirmBtn = this.page.getByRole('button', { name: /да|подтвер|confirm|yes/i });
    if (await confirmBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await confirmBtn.click();
    }
    // Ждём исчезновения сообщения вместо фиксированного timeout
    await this.expectMessageNotVisible(messageText);
  }

  async addReaction(messageText: string, emoji = '👍') {
    await this.openMessageActions(messageText);
    // Реакции отображаются в верхней части контекстного меню
    const reactionBtn = this.page.locator('[class*="contextMenuReactions"] button, [class*="contextMenuReactions"] [role="button"]')
      .filter({ hasText: emoji }).first();
    if (await reactionBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await reactionBtn.click();
    } else {
      // Fallback: ищем emoji текст
      await this.page.locator(`text="${emoji}"`).first().click();
    }
  }

  async pinMessage(messageText: string) {
    await this.openMessageActions(messageText);
    await this.page.locator('[class*="contextMenuItem"]').filter({ hasText: /закреп|pin/i }).first().click();
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
