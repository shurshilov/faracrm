import type { Page } from '@playwright/test';
import { test, expect } from '../../fixtures';
import { ApiHelper, Session } from '../../helpers/api.helper';
import { ChatPage, SettingsTab } from '../../pages/ChatPage';

/**
 * Окно «Настройки чата» группы: кто что в нём может.
 *
 * Чатом управляют его админ и суперпользователь — тот в любой группе, даже не
 * состоя в ней: название и описание, права по умолчанию, права участников,
 * удаление чата. Обычному участнику настройки видны, но недоступны; он может
 * покинуть чат, а с правом приглашать — добавить участника. Последний админ
 * покидает чат, только передав права.
 *
 * Пользователи из global-setup: admin — суперпользователь (page открыт под
 * ним), user2 = test1 (user2Page) и user3 = test2 — обычные сотрудники.
 */

const CHAT_NAME = /^(название чата|chat name)$/i;
const DESCRIPTION = /^(описание|description)$/i;
const LEAVE_CHAT = /^(покинуть чат|leave chat)$/i;
const DELETE_CHAT = /^(удалить чат|delete chat)$/i;
const ADD_MEMBER = /^(добавить участника|add member)$/i;
const MEMBER_RIGHTS = /права участника|member permissions/i;
const MEMBER_REMOVE = /удалить участника|remove member/i;
const ADMIN_BADGE = /^(админ|admin)$/i;
const READ_ONLY_BADGE = /^(только чтение|read only)$/i;
const LAST_ADMIN =
  /это последний администратор чата|this is the last chat admin/i;

/**
 * Группа с первым сообщением: список чатов отсортирован по дате последнего
 * сообщения, без него чат оказался бы в самом конце.
 */
async function createGroup(
  api: ApiHelper,
  owner: Session,
  memberIds: number[],
): Promise<{ id: number; name: string }> {
  const name = `E2E Settings ${Date.now()}`;
  const { id } = await api.createChat(owner, { name, user_ids: memberIds });
  await api.sendMessage(owner, id, 'Привет');
  return { id, name };
}

/** Открыть чат и его настройки на вкладке. */
async function openSettings(
  page: Page,
  chatName: string,
  tab: SettingsTab = 'main',
): Promise<ChatPage> {
  const chat = new ChatPage(page);
  await chat.goto();
  await chat.openChat(chatName);
  await chat.openSettings(tab);
  return chat;
}

/** Ответ бэкенда на запрос страницы. */
function apiResponse(page: Page, method: string, path: string) {
  return page.waitForResponse(
    r => r.request().method() === method && r.url().endsWith(path),
  );
}

test.describe('Настройки чата — суперпользователь', () => {
  // Группу создаёт user2 — админ чата он, суперпользователь в ней обычный
  // участник. Из такого чата пришёл отчёт «права не изменить даже админу».
  let chatId: number;
  let chatName: string;

  test.beforeEach(async ({ api, adminSession, user2Session, user3Session }) => {
    ({ id: chatId, name: chatName } = await createGroup(api, user2Session, [
      adminSession.user_id.id,
      user3Session.user_id.id,
    ]));
  });

  test.afterEach(async ({ api, adminSession }) => {
    await api.deleteChat(adminSession, chatId).catch(() => {});
  });

  test('меняет права по умолчанию, не будучи админом чата', async ({
    page,
    api,
    adminSession,
    user2Session,
  }) => {
    expect(await api.getChatAdminIds(adminSession, chatId)).toEqual([
      user2Session.user_id.id,
    ]);

    const chat = await openSettings(page, chatName, 'permissions');
    const dialog = chat.settingsDialog;
    await chat.setRight(dialog, 'invite', true);

    const saved = apiResponse(page, 'PATCH', `/chats/${chatId}`);
    await chat.saveButton(dialog).click();
    expect((await saved).ok()).toBeTruthy();

    const { default_can_invite } = await api.getChat(adminSession, chatId);
    expect(default_can_invite).toBe(true);
  });

  test('меняет права участника', async ({
    page,
    api,
    adminSession,
    user3Session,
  }) => {
    const { id: user3Id, name: user3Name } = user3Session.user_id;
    const chat = await openSettings(page, chatName, 'members');

    await chat.memberRightsButton(user3Name).click();
    const rights = chat.memberRightsDialog;
    await chat.setRight(rights, 'write', false);
    const saved = apiResponse(
      page,
      'PATCH',
      `/chats/${chatId}/members/${user3Id}/permissions`,
    );
    await chat.saveButton(rights).click();
    expect((await saved).ok()).toBeTruthy();

    // Окно прав закрылось, список перечитан: участник больше не пишет
    await expect(rights).toBeHidden();
    await expect(chat.settingsDialog.getByText(READ_ONLY_BADGE)).toBeVisible();
    const members = await api.getChatMembers(adminSession, chatId);
    expect(members.find(m => m.id === user3Id)?.permissions.can_write).toBe(
      false,
    );
  });

  test('назначает админа чата', async ({
    page,
    api,
    adminSession,
    user2Session,
    user3Session,
  }) => {
    const { id: user3Id, name: user3Name } = user3Session.user_id;
    const chat = await openSettings(page, chatName, 'members');

    await chat.memberRightsButton(user3Name).click();
    const rights = chat.memberRightsDialog;
    await chat.setRight(rights, 'admin', true);
    const saved = apiResponse(
      page,
      'PATCH',
      `/chats/${chatId}/members/${user3Id}/permissions`,
    );
    await chat.saveButton(rights).click();
    expect((await saved).ok()).toBeTruthy();

    // В списке два админа: создатель группы и назначенный
    await expect(chat.settingsDialog.getByText(ADMIN_BADGE)).toHaveCount(2);
    expect(await api.getChatAdminIds(adminSession, chatId)).toEqual(
      [user2Session.user_id.id, user3Id].sort((a, b) => a - b),
    );
  });

  test('удаляет участника', async ({
    page,
    api,
    adminSession,
    user3Session,
  }) => {
    const { id: user3Id, name: user3Name } = user3Session.user_id;
    const chat = await openSettings(page, chatName, 'members');

    const removed = apiResponse(
      page,
      'DELETE',
      `/chats/${chatId}/members/${user3Id}`,
    );
    await chat.memberRemoveButton(user3Name).click();
    expect((await removed).ok()).toBeTruthy();

    await expect(chat.memberRemoveButton(user3Name)).toHaveCount(0);
    const members = await api.getChatMembers(adminSession, chatId);
    expect(members.map(m => m.id)).not.toContain(user3Id);
  });

  test('переименовывает чат', async ({ page, api, adminSession }) => {
    const chat = await openSettings(page, chatName);
    const dialog = chat.settingsDialog;
    const newName = `${chatName} renamed`;
    await dialog.getByLabel(CHAT_NAME).fill(newName);

    const saved = apiResponse(page, 'PATCH', `/chats/${chatId}`);
    await chat.saveButton(dialog).click();
    expect((await saved).ok()).toBeTruthy();

    await expect(dialog).toBeHidden();
    await chat.expectChatInList(newName);
    expect((await api.getChat(adminSession, chatId)).name).toBe(newName);
  });
});

test.describe('Настройки чата — суперпользователь в чужом чате', () => {
  // В группе user2 и user3, суперпользователь в ней не состоит
  let chatId: number;
  let chatName: string;

  test.beforeEach(async ({ api, user2Session, user3Session }) => {
    ({ id: chatId, name: chatName } = await createGroup(api, user2Session, [
      user3Session.user_id.id,
    ]));
  });

  test.afterEach(async ({ api, adminSession }) => {
    await api.deleteChat(adminSession, chatId).catch(() => {});
  });

  test('открывает чат и назначает в нём админа', async ({
    page,
    api,
    adminSession,
    user2Session,
    user3Session,
  }) => {
    const { id: user3Id, name: user3Name } = user3Session.user_id;
    const chat = new ChatPage(page);
    await chat.goto();
    await chat.showForeignChats();
    // Ждём сам чат: не найдя его сразу, openChat перезагрузит страницу, а
    // переключатель чужих чатов между загрузками не хранится
    await expect(page.getByText(chatName).first()).toBeVisible();
    await chat.openChat(chatName);
    await chat.openSettings();
    const dialog = chat.settingsDialog;

    // Не участник: покидать нечего, а удалить чат можно
    await expect(
      dialog.getByRole('button', { name: DELETE_CHAT }),
    ).toBeVisible();
    await expect(dialog.getByRole('button', { name: LEAVE_CHAT })).toHaveCount(
      0,
    );

    await chat.openSettingsTab('members');
    await chat.memberRightsButton(user3Name).click();
    const rights = chat.memberRightsDialog;
    await chat.setRight(rights, 'admin', true);
    const saved = apiResponse(
      page,
      'PATCH',
      `/chats/${chatId}/members/${user3Id}/permissions`,
    );
    await chat.saveButton(rights).click();
    expect((await saved).ok()).toBeTruthy();

    expect(await api.getChatAdminIds(adminSession, chatId)).toEqual(
      [user2Session.user_id.id, user3Id].sort((a, b) => a - b),
    );
    // Участником чата суперпользователь при этом не стал
    const members = await api.getChatMembers(adminSession, chatId);
    expect(members.map(m => m.id)).not.toContain(adminSession.user_id.id);
  });

  test('управляет участниками и удаляет чат (API)', async ({
    api,
    adminSession,
    user3Session,
  }) => {
    const adminId = adminSession.user_id.id;
    const user3Id = user3Session.user_id.id;
    const membersPath = `/chats/${chatId}/members`;

    const removed = await api.request(
      adminSession,
      'DELETE',
      `${membersPath}/${user3Id}`,
    );
    expect(removed.status).toBe(200);
    // Добавить можно и себя
    const added = await api.request(adminSession, 'POST', membersPath, {
      user_id: adminId,
    });
    expect(added.status).toBe(200);
    const members = await api.getChatMembers(adminSession, chatId);
    expect(members.map(m => m.id)).toContain(adminId);
    expect(members.map(m => m.id)).not.toContain(user3Id);

    const deleted = await api.request(
      adminSession,
      'DELETE',
      `/chats/${chatId}`,
    );
    expect(deleted.status).toBe(200);
  });
});

test.describe('Настройки чата — админ чата', () => {
  // user2 создал группу — он её единственный админ, user3 — участник
  let chatId: number;
  let chatName: string;

  test.beforeEach(async ({ api, user2Session, user3Session }) => {
    ({ id: chatId, name: chatName } = await createGroup(api, user2Session, [
      user3Session.user_id.id,
    ]));
  });

  test.afterEach(async ({ api, adminSession }) => {
    await api.deleteChat(adminSession, chatId).catch(() => {});
  });

  test('меняет права по умолчанию — их получает новый участник', async ({
    user2Page,
    api,
    adminSession,
    user2Session,
  }) => {
    const chat = await openSettings(user2Page, chatName, 'permissions');
    const dialog = chat.settingsDialog;
    await chat.setRight(dialog, 'invite', true);
    await chat.setRight(dialog, 'write', false);

    const saved = apiResponse(user2Page, 'PATCH', `/chats/${chatId}`);
    await chat.saveButton(dialog).click();
    expect((await saved).ok()).toBeTruthy();

    const adminId = adminSession.user_id.id;
    const added = await api.request(
      user2Session,
      'POST',
      `/chats/${chatId}/members`,
      { user_id: adminId },
    );
    expect(added.status).toBe(200);
    const members = await api.getChatMembers(user2Session, chatId);
    expect(members.find(m => m.id === adminId)?.permissions).toMatchObject({
      can_invite: true,
      can_write: false,
      is_admin: false,
    });
  });

  test('даёт участнику право приглашать', async ({
    user2Page,
    api,
    user2Session,
    user3Session,
  }) => {
    const { id: user3Id, name: user3Name } = user3Session.user_id;
    const chat = await openSettings(user2Page, chatName, 'members');

    await chat.memberRightsButton(user3Name).click();
    const rights = chat.memberRightsDialog;
    await chat.setRight(rights, 'invite', true);
    const saved = apiResponse(
      user2Page,
      'PATCH',
      `/chats/${chatId}/members/${user3Id}/permissions`,
    );
    await chat.saveButton(rights).click();
    expect((await saved).ok()).toBeTruthy();

    const members = await api.getChatMembers(user2Session, chatId);
    expect(members.find(m => m.id === user3Id)?.permissions).toMatchObject({
      can_invite: true,
      is_admin: false,
    });
  });

  test('меняет название и описание', async ({
    user2Page,
    api,
    user2Session,
  }) => {
    const chat = await openSettings(user2Page, chatName);
    const dialog = chat.settingsDialog;
    const newName = `${chatName} renamed`;
    await dialog.getByLabel(CHAT_NAME).fill(newName);
    await dialog.getByLabel(DESCRIPTION).fill('Рабочая группа');

    const saved = apiResponse(user2Page, 'PATCH', `/chats/${chatId}`);
    await chat.saveButton(dialog).click();
    expect((await saved).ok()).toBeTruthy();

    await expect(dialog).toBeHidden();
    await chat.expectChatInList(newName);
    expect(await api.getChat(user2Session, chatId)).toMatchObject({
      name: newName,
      description: 'Рабочая группа',
    });
  });

  test('последний админ не может покинуть чат', async ({
    user2Page,
    api,
    user2Session,
  }) => {
    const chat = await openSettings(user2Page, chatName);

    const refused = apiResponse(user2Page, 'POST', `/chats/${chatId}/leave`);
    await chat.settingsDialog.getByRole('button', { name: LEAVE_CHAT }).click();
    expect((await refused).status()).toBe(400);

    await expect(
      user2Page.getByRole('dialog', { name: LAST_ADMIN }),
    ).toBeVisible();
    expect(await api.getChatAdminIds(user2Session, chatId)).toEqual([
      user2Session.user_id.id,
    ]);
  });

  test('передаёт права и покидает чат', async ({
    user2Page,
    api,
    user2Session,
    user3Session,
  }) => {
    const { id: user3Id, name: user3Name } = user3Session.user_id;
    const chat = await openSettings(user2Page, chatName, 'members');

    await chat.memberRightsButton(user3Name).click();
    const rights = chat.memberRightsDialog;
    await chat.setRight(rights, 'admin', true);
    const saved = apiResponse(
      user2Page,
      'PATCH',
      `/chats/${chatId}/members/${user3Id}/permissions`,
    );
    await chat.saveButton(rights).click();
    expect((await saved).ok()).toBeTruthy();
    await expect(rights).toBeHidden();

    await chat.openSettingsTab('main');
    const left = apiResponse(user2Page, 'POST', `/chats/${chatId}/leave`);
    await chat.settingsDialog.getByRole('button', { name: LEAVE_CHAT }).click();
    expect((await left).ok()).toBeTruthy();

    await chat.expectChatNotInList(chatName);
    expect(await api.getChatAdminIds(user3Session, chatId)).toEqual([user3Id]);
    const members = await api.getChatMembers(user3Session, chatId);
    expect(members.map(m => m.id)).not.toContain(user2Session.user_id.id);
  });

  test('удаляет чат', async ({ user2Page, api, user3Session }) => {
    const chat = await openSettings(user2Page, chatName);

    // Удаление подтверждается системным окном confirm
    user2Page.once('dialog', confirm => confirm.accept());
    const deleted = apiResponse(user2Page, 'DELETE', `/chats/${chatId}`);
    await chat.settingsDialog
      .getByRole('button', { name: DELETE_CHAT })
      .click();
    expect((await deleted).ok()).toBeTruthy();

    await chat.expectChatNotInList(chatName);
    // Пропал и у второго участника
    const listed = await api.request(user3Session, 'GET', '/chats?limit=100');
    const { data } = await listed.json();
    expect(data.map((c: { id: number }) => c.id)).not.toContain(chatId);
  });
});

test.describe('Настройки чата — обычный участник', () => {
  // Группу создал user3 — админ чата он, user2 — участник без прав
  let chatId: number;
  let chatName: string;

  test.beforeEach(async ({ api, user2Session, user3Session }) => {
    ({ id: chatId, name: chatName } = await createGroup(api, user3Session, [
      user2Session.user_id.id,
    ]));
  });

  test.afterEach(async ({ api, adminSession }) => {
    await api.deleteChat(adminSession, chatId).catch(() => {});
  });

  test('видит настройки, но менять их не может', async ({ user2Page }) => {
    const chat = await openSettings(user2Page, chatName);
    const dialog = chat.settingsDialog;

    // «Основное»: название и описание не редактируются, удалить чат нельзя
    await expect(dialog.getByLabel(CHAT_NAME)).toBeDisabled();
    await expect(dialog.getByLabel(DESCRIPTION)).toBeDisabled();
    await expect(chat.saveButton(dialog)).toBeDisabled();
    await expect(dialog.getByRole('button', { name: DELETE_CHAT })).toHaveCount(
      0,
    );
    await expect(
      dialog.getByRole('button', { name: LEAVE_CHAT }),
    ).toBeEnabled();

    // «Права»: переключатели прав по умолчанию и «Сохранить» выключены
    await chat.openSettingsTab('permissions');
    const switches = dialog.getByRole('switch');
    await expect(switches).toHaveCount(6);
    for (const rightSwitch of await switches.all()) {
      await expect(rightSwitch).toBeDisabled();
    }
    await expect(chat.saveButton(dialog)).toBeDisabled();

    // «Участники»: ни прав участников, ни удаления, ни добавления
    await chat.openSettingsTab('members');
    await expect(dialog.getByText(ADMIN_BADGE)).toBeVisible();
    await expect(
      dialog.getByRole('button', { name: MEMBER_RIGHTS }),
    ).toHaveCount(0);
    await expect(
      dialog.getByRole('button', { name: MEMBER_REMOVE }),
    ).toHaveCount(0);
    await expect(dialog.getByRole('button', { name: ADD_MEMBER })).toHaveCount(
      0,
    );
  });

  test('не меняет настройки в обход окна (API)', async ({
    api,
    user2Session,
    user3Session,
  }) => {
    const user2Id = user2Session.user_id.id;
    const denied = [
      await api.request(user2Session, 'PATCH', `/chats/${chatId}`, {
        default_can_invite: true,
      }),
      await api.request(
        user2Session,
        'PATCH',
        `/chats/${chatId}/members/${user2Id}/permissions`,
        { is_admin: true },
      ),
      await api.request(user2Session, 'DELETE', `/chats/${chatId}`),
    ];
    expect(denied.map(r => r.status)).toEqual([403, 403, 403]);

    const info = await api.getChat(user3Session, chatId);
    expect(info.default_can_invite).toBe(false);
    expect(await api.getChatAdminIds(user3Session, chatId)).toEqual([
      user3Session.user_id.id,
    ]);
  });

  test('покидает чат', async ({
    user2Page,
    api,
    user2Session,
    user3Session,
  }) => {
    const chat = await openSettings(user2Page, chatName);

    const left = apiResponse(user2Page, 'POST', `/chats/${chatId}/leave`);
    await chat.settingsDialog.getByRole('button', { name: LEAVE_CHAT }).click();
    expect((await left).ok()).toBeTruthy();

    await chat.expectChatNotInList(chatName);
    const members = await api.getChatMembers(user3Session, chatId);
    expect(members.map(m => m.id)).not.toContain(user2Session.user_id.id);
  });

  test('с правом приглашать добавляет участника, но прав не меняет', async ({
    user2Page,
    api,
    adminSession,
    user2Session,
    user3Session,
  }) => {
    const { id: adminId, name: adminName } = adminSession.user_id;
    const membersPath = `/chats/${chatId}/members`;
    const granted = await api.request(
      user3Session,
      'PATCH',
      `${membersPath}/${user2Session.user_id.id}/permissions`,
      { can_invite: true },
    );
    expect(granted.status).toBe(200);

    const chat = await openSettings(user2Page, chatName, 'members');
    const dialog = chat.settingsDialog;
    await expect(dialog.getByText(ADMIN_BADGE)).toBeVisible();
    await expect(
      dialog.getByRole('button', { name: MEMBER_RIGHTS }),
    ).toHaveCount(0);
    await expect(
      dialog.getByRole('button', { name: MEMBER_REMOVE }),
    ).toHaveCount(0);

    const search = dialog.getByPlaceholder(/поиск пользователей|search users/i);
    await search.fill(adminName);
    await user2Page
      .getByRole('option', { name: adminName, exact: true })
      .click();
    // Закрыть выпадающий список, чтобы он не перекрыл кнопку
    await search.press('Tab');

    const added = apiResponse(user2Page, 'POST', membersPath);
    await dialog.getByRole('button', { name: ADD_MEMBER }).click();
    expect((await added).ok()).toBeTruthy();

    const members = await api.getChatMembers(user3Session, chatId);
    expect(members.map(m => m.id)).toContain(adminId);
  });
});
