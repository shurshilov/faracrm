import { test, expect } from '../../fixtures';
import { ApiHelper, Session } from '../../helpers/api.helper';
import { ChatPage } from '../../pages/ChatPage';

/**
 * Участники группового чата. В группе без админа добавляемый пользователь
 * становится админом: создатель группы, у чата партнёра — первый пришедший.
 * Последний админ выходит из чата, только передав права другому. Админ
 * добавляет и удаляет участников, остальным — только с правом приглашать
 * (can_invite) или удалять (can_remove); без права кнопки в окне настроек
 * чата нет.
 *
 * Пользователи из global-setup: admin, user2 = test1, user3 = test2.
 */

async function adminIds(
  api: ApiHelper,
  session: Session,
  chatId: number,
): Promise<number[]> {
  const members = await api.getChatMembers(session, chatId);
  return members
    .filter(m => m.member_type === 'user' && m.permissions.is_admin)
    .map(m => m.id);
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

test.describe('Чат — администратор группы (API)', () => {
  // Чаты удаляет их админ: системный администратор без членства не может
  let cleanup: { session: Session; chatId: number }[] = [];

  test.afterEach(async ({ api }) => {
    for (const { session, chatId } of cleanup) {
      await api.deleteChat(session, chatId).catch(() => {});
    }
    cleanup = [];
  });

  test('создатель — админ: добавляет и удаляет, добавленный пишет', async ({
    api,
    adminSession,
    user2Session,
    user3Session,
  }) => {
    const adminId = adminSession.user_id.id;
    const { id: chatId } = await api.createChat(user2Session, {
      name: `E2E Admin ${Date.now()}`,
      user_ids: [user3Session.user_id.id],
    });
    cleanup.push({ session: user2Session, chatId });

    expect(await adminIds(api, user2Session, chatId)).toEqual([
      user2Session.user_id.id,
    ]);

    // Не-админ не управляет участниками
    const membersPath = `/chats/${chatId}/members`;
    const denied = await api.request(user3Session, 'POST', membersPath, {
      user_id: adminId,
    });
    expect(denied.status).toBe(403);

    const added = await api.request(user2Session, 'POST', membersPath, {
      user_id: adminId,
    });
    expect(added.status).toBe(200);
    // Добавленный получил права чата по умолчанию — может писать
    await api.sendMessage(adminSession, chatId, 'Меня добавили');

    const adminPath = `${membersPath}/${adminId}`;
    const notRemoved = await api.request(user3Session, 'DELETE', adminPath);
    expect(notRemoved.status).toBe(403);

    const removed = await api.request(user2Session, 'DELETE', adminPath);
    expect(removed.status).toBe(200);
    const members = await api.getChatMembers(user2Session, chatId);
    expect(members.map(m => m.id)).not.toContain(adminId);
  });

  test('последний админ выходит, только передав права', async ({
    api,
    user2Session,
    user3Session,
  }) => {
    const user3Id = user3Session.user_id.id;
    const { id: chatId } = await api.createChat(user2Session, {
      name: `E2E Last admin ${Date.now()}`,
      user_ids: [user3Id],
    });
    // Удалит тот, кто к концу теста админ
    cleanup.push(
      { session: user2Session, chatId },
      { session: user3Session, chatId },
    );

    const leavePath = `/chats/${chatId}/leave`;
    const refused = await api.request(user2Session, 'POST', leavePath);
    expect(refused.status).toBe(400);
    expect((await refused.json()).content).toBe(
      'CANNOT_REMOVE_THE_LAST_CHAT_ADMIN',
    );

    const handedOver = await api.request(
      user2Session,
      'PATCH',
      `/chats/${chatId}/members/${user3Id}/permissions`,
      { is_admin: true },
    );
    expect(handedOver.status).toBe(200);
    const left = await api.request(user2Session, 'POST', leavePath);
    expect(left.status).toBe(200);

    expect(await adminIds(api, user3Session, chatId)).toEqual([user3Id]);
  });

  test('чат партнёра из карточки — админ нажавший «Создать чат»', async ({
    api,
    adminSession,
    user2Session,
  }) => {
    const partner = await api.createRecord(adminSession, 'partners', {
      name: `E2E Client ${Date.now()}`,
    });
    const partnerId = partner.id ?? partner.data?.id;

    const res = await api.request(
      user2Session,
      'POST',
      `/partners/${partnerId}/chat`,
    );
    expect(res.status).toBe(200);
    const { chat_id: chatId } = await res.json();
    cleanup.push({ session: user2Session, chatId });

    expect(await adminIds(api, user2Session, chatId)).toEqual([
      user2Session.user_id.id,
    ]);
  });
});

test.describe('Чат — участники в окне настроек (UI)', () => {
  let chatId: number;
  let chatName: string;

  test.beforeEach(async ({ api, adminSession, user2Session }) => {
    chatName = `E2E Members ${Date.now()}`;
    const chat = await api.createChat(adminSession, {
      name: chatName,
      user_ids: [user2Session.user_id.id],
    });
    chatId = chat.id;
  });

  test.afterEach(async ({ api, adminSession }) => {
    await api.deleteChat(adminSession, chatId).catch(() => {});
  });

  test('админ добавляет и удаляет участника', async ({
    page,
    api,
    adminSession,
    user3Session,
  }) => {
    const { id: user3Id, name: user3Name } = user3Session.user_id;
    const chat = new ChatPage(page);
    await chat.goto();
    await chat.openChat(chatName);
    await chat.openMembersSettings();
    const dialog = page.getByRole('dialog');

    const search = dialog.getByPlaceholder(/поиск пользователей|search users/i);
    await search.fill(user3Name);
    await page.getByRole('option', { name: user3Name }).click();
    // Закрыть выпадающий список, чтобы он не перекрыл кнопку
    await search.press('Tab');

    const added = page.waitForResponse(
      r =>
        r.url().endsWith(`/chats/${chatId}/members`) &&
        r.request().method() === 'POST',
    );
    await dialog
      .getByRole('button', { name: /^(добавить участника|add member)$/i })
      .click();
    expect((await added).ok()).toBeTruthy();

    const removeButton = dialog.getByRole('button', {
      name: new RegExp(
        `(удалить участника|remove member): ${escapeRegExp(user3Name)}`,
        'i',
      ),
    });
    await expect(removeButton).toBeVisible();

    const removed = page.waitForResponse(
      r =>
        r.url().endsWith(`/chats/${chatId}/members/${user3Id}`) &&
        r.request().method() === 'DELETE',
    );
    await removeButton.click();
    expect((await removed).ok()).toBeTruthy();
    await expect(removeButton).toHaveCount(0);

    const members = await api.getChatMembers(adminSession, chatId);
    expect(members.map(m => m.id)).not.toContain(user3Id);
  });

  test('обычный участник не видит управления участниками', async ({
    user2Page,
  }) => {
    const chat = new ChatPage(user2Page);
    await chat.goto();
    await chat.openChat(chatName);
    await chat.openMembersSettings();
    const dialog = user2Page.getByRole('dialog');

    // Список загрузился: у создателя чата — бейдж админа
    await expect(dialog.getByText(/^(админ|admin)$/i)).toBeVisible();
    await expect(
      dialog.getByRole('button', {
        name: /^(добавить участника|add member)$/i,
      }),
    ).toHaveCount(0);
    await expect(
      dialog.getByRole('button', { name: /удалить участника|remove member/i }),
    ).toHaveCount(0);
  });

  test('участник с правом удалять видит только удаление', async ({
    user2Page,
    api,
    adminSession,
    user2Session,
    user3Session,
  }) => {
    const { id: user3Id, name: user3Name } = user3Session.user_id;
    const membersPath = `/chats/${chatId}/members`;
    const added = await api.request(adminSession, 'POST', membersPath, {
      user_id: user3Id,
    });
    expect(added.status).toBe(200);
    const granted = await api.request(
      adminSession,
      'PATCH',
      `${membersPath}/${user2Session.user_id.id}/permissions`,
      { can_remove: true },
    );
    expect(granted.status).toBe(200);

    const chat = new ChatPage(user2Page);
    await chat.goto();
    await chat.openChat(chatName);
    await chat.openMembersSettings();
    const dialog = user2Page.getByRole('dialog');

    const removeButton = dialog.getByRole('button', {
      name: new RegExp(
        `(удалить участника|remove member): ${escapeRegExp(user3Name)}`,
        'i',
      ),
    });
    await expect(removeButton).toBeVisible();
    await expect(
      dialog.getByRole('button', {
        name: /^(добавить участника|add member)$/i,
      }),
    ).toHaveCount(0);
    await expect(
      dialog.getByRole('button', {
        name: /права участника|member permissions/i,
      }),
    ).toHaveCount(0);

    const removed = user2Page.waitForResponse(
      r =>
        r.url().endsWith(`${membersPath}/${user3Id}`) &&
        r.request().method() === 'DELETE',
    );
    await removeButton.click();
    expect((await removed).ok()).toBeTruthy();

    const members = await api.getChatMembers(adminSession, chatId);
    expect(members.map(m => m.id)).not.toContain(user3Id);
  });
});
