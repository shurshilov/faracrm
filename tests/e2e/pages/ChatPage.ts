import { Page, Locator, expect } from '@playwright/test';

/** Вкладки окна «Настройки чата» группы. */
const SETTINGS_TABS = {
  main: /^(основное|main)$/i,
  members: /^(участники|members)$/i,
  permissions: /^(права|permissions)$/i,
};
export type SettingsTab = keyof typeof SETTINGS_TABS;

/** Права: подписи переключателей в настройках чата и в окне прав участника. */
const CHAT_RIGHTS = {
  read: /может читать сообщения|can read messages/i,
  write: /может отправлять сообщения|can send messages/i,
  invite: /может приглашать участников|can invite members/i,
  remove: /может удалять участников|can remove members/i,
  pin: /может закреплять сообщения|can pin messages/i,
  deleteOthers: /может удалять чужие сообщения|can delete others' messages/i,
  admin: /^(администратор|administrator)$/i,
};
export type ChatRight = keyof typeof CHAT_RIGHTS;

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Page Object для страницы чата.
 *
 * Структура UI:
 * - Sidebar (ChatSections): квадраты разделов (Сотрудники/Клиенты/Каналы/
 *   Документы) + свои папки; фильтры раздела — чипы над списком
 * - Main: ChatPage = ChatList (список чатов) + ChatMessages (сообщения)
 *
 * URL: /chat — раздел «Сотрудники» (внутренние чаты), /chat?section=clients…
 */
export class ChatPage {
  readonly newChatButton: Locator;
  readonly messageInput: Locator;
  readonly sendButton: Locator;
  readonly messagesContainer: Locator;

  constructor(private page: Page) {
    // Английский заголовок — как в fara_chat/locales/en.json ("New Chat").
    this.newChatButton = page.locator('[title="Новый чат"], [title="New Chat"]').first();
    this.messageInput = page.getByPlaceholder(/введите сообщение|type.*message/i).first();
    this.sendButton = page.locator(
      'button[class*="send"], [class*="ChatInput"] button[type="submit"]',
    ).last();
    // Ограничиваем messagesContainer правой частью (chatArea) — 
    // исключаем sidebar со списком чатов, где отображается last_message preview
    this.messagesContainer = page.locator('[class*="chatArea"], [class*="chat-area"]').first();
  }

  /**
   * Перейти на страницу чатов и загрузить список внутренних чатов
   * (квадрат «Сотрудники» в sidebar).
   */
  async goto() {
    // Переходим на /chat
    await this.page.goto('/chat');
    await this.page.waitForLoadState('networkidle');

    await this._openStaff();

    // Ждём загрузки ChatList — input поиска или список чатов
    await this._waitForChatList();
  }

  /** Кликнуть квадрат «Сотрудники» в sidebar */
  private async _openStaff() {
    const staffTile = this.page
      .getByRole('button', { name: /^(сотрудники|staff)$/i })
      .first();
    await staffTile.waitFor({ state: 'visible', timeout: 10_000 });
    await staffTile.click();
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
      // ChatList мог не загрузиться — попробуем ещё раз открыть «Сотрудники»
      await this._openStaff();
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
      await this._openStaff();
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
      await this._openStaff();
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

    // Ждём появления модалки. Используем role="dialog" вместо поиска по
    // заголовку — устойчивее к изменениям перевода и UI.
    await expect(this.page.getByRole('dialog').first()).toBeVisible({
      timeout: 5_000,
    });

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

  // ==================== Настройки чата ====================

  /** Окно «Настройки чата». */
  get settingsDialog(): Locator {
    return this.page.getByRole('dialog', {
      name: /настройки чата|chat settings/i,
    });
  }

  /** Окно «Права участника» — открывается поверх настроек чата. */
  get memberRightsDialog(): Locator {
    return this.page.getByRole('dialog', {
      name: /права участника|member permissions/i,
    });
  }

  /** Открыть настройки открытого чата (группы) на нужной вкладке. */
  async openSettings(tab: SettingsTab = 'main') {
    // «Опции» есть и у строк списка чатов — берём кнопку в шапке чата
    await this.messagesContainer.getByTitle(/^(опции|options)$/i).click();
    await this.page
      .getByRole('menuitem', { name: /^(настройки|settings)$/i })
      .click();
    await this.openSettingsTab(tab);
  }

  /**
   * Перейти на вкладку окна настроек. Вкладки появляются, когда чат
   * загружен — с участниками и их правами.
   */
  async openSettingsTab(tab: SettingsTab) {
    await this.settingsDialog
      .getByRole('tab', { name: SETTINGS_TABS[tab] })
      .click();
  }

  /** «Сохранить» открытой вкладки настроек или окна прав участника. */
  saveButton(dialog: Locator): Locator {
    return dialog.getByRole('button', { name: /^(сохранить|save)$/i });
  }

  /** Кнопка-щит «Права участника» в строке участника. */
  memberRightsButton(memberName: string): Locator {
    return this.settingsDialog.getByRole('button', {
      name: new RegExp(
        `(права участника|member permissions): ${escapeRegExp(memberName)}`,
        'i',
      ),
    });
  }

  /** Кнопка удаления участника в его строке. */
  memberRemoveButton(memberName: string): Locator {
    return this.settingsDialog.getByRole('button', {
      name: new RegExp(
        `(удалить участника|remove member): ${escapeRegExp(memberName)}`,
        'i',
      ),
    });
  }

  /**
   * Включить или выключить право: в настройках чата — право по умолчанию,
   * в окне прав участника — его право.
   */
  async setRight(dialog: Locator, right: ChatRight, checked: boolean) {
    await this.setSwitch(
      dialog.getByRole('switch', { name: CHAT_RIGHTS[right] }),
      checked,
    );
  }

  /**
   * Показать в списке чаты, где пользователь не участник (опция
   * суперпользователя). Между загрузками страницы не хранится.
   */
  async showForeignChats() {
    await this.page
      .getByTitle(/^(настройки списка|list settings)$/i)
      .click();
    await this.setSwitch(
      this.page.getByRole('switch', {
        name: /показывать чужие чаты|show others' chats/i,
      }),
      true,
    );
    await this.page.keyboard.press('Escape');
  }

  /**
   * Переключатель Mantine. Его input прозрачный и лежит под дорожкой: клик
   * мышью по нему Playwright считает перехваченным, поэтому жмём пробел.
   */
  private async setSwitch(sw: Locator, checked: boolean) {
    await expect(sw).toBeEnabled();
    if ((await sw.isChecked()) !== checked) await sw.press('Space');
    await expect(sw).toBeChecked({ checked });
  }

  // ==================== Сообщения ====================

  async sendMessage(text: string) {
    await this.messageInput.waitFor({ state: 'visible', timeout: 10_000 });
    await this.messageInput.click();
    await this.messageInput.clear();
    await this.messageInput.pressSequentially(text, { delay: 10 });

    // Перехватываем ответ сервера
    const responsePromise = this.page.waitForResponse(
      resp => resp.url().includes('/messages') && resp.request().method() === 'POST',
      { timeout: 15_000 },
    );

    await this.page.keyboard.press('Enter');

    const response = await responsePromise;
    if (!response.ok()) {
      const body = await response.text().catch(() => 'no body');
      throw new Error(
        `POST messages failed: ${response.status()} ${response.statusText()} — ${body}`,
      );
    }

    // После POST сервер ответил 200. Сообщение появится на странице
    // через один из путей:
    // 1. Оптимистик-апдейт RTK Query (мгновенно, если кеш инициализирован)
    // 2. invalidatesTags → refetch getChatMessages (через ~100-300ms)
    // 3. WebSocket new_message (для других участников)
    // Ждём появления текста на странице.
    await expect(
      this.page.getByText(text, { exact: false }).first(),
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
    // Кликаем "Сохранить" и ждём API ответ
    const [response] = await Promise.all([
      this.page.waitForResponse(
        (res: any) => res.url().includes('/message') && (res.request().method() === 'PUT' || res.request().method() === 'PATCH'),
        { timeout: 10_000 },
      ).catch(() => null),
      this.page.getByRole('button', { name: /сохранить|save/i }).click(),
    ]);
    // Ждём закрытия модалки
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
