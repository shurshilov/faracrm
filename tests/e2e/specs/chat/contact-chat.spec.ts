import { test, expect, Page } from '../../fixtures';
import { ChatPage } from '../../pages/ChatPage';
import { Session } from '../../helpers/api.helper';

/**
 * Чат по значку контакта (issue #47).
 *
 * Значок мессенджера/email у контакта в карточке партнёра или сотрудника
 * открывает «Общение»: чат есть — он открывается сразу с каналом этого
 * контакта; чата нет — визард создания с уже выбранным собеседником (клиент →
 * «Группа» с именем партнёра на вкладке «Партнёры», сотрудник → «Личный» на
 * вкладке «Пользователи»), создаёт пользователь кнопкой. В визарде у
 * участников, чат с которыми уже есть, бейдж «есть чат» — клик по нему
 * открывает тот чат. Значок телефона подставляет номер в звонилку.
 *
 * Пользователи из global-setup: admin, user3 = test2 («Test User 2»).
 */

const PARTNER_NAME = `E2E Contact ${Date.now()}`;
const PARTNER_EMAIL = `contact${Date.now()}@example.com`;
const USER_TELEGRAM = `tg_e2e_${Date.now()}`;

let partnerId: number;
let partnerContactId: number;
let userContactId: number;
let partnerChatId: number | null = null;
let directChatId: number | null = null;

/**
 * Значок контакта с данным значением: у записи может быть несколько
 * контактов, у каждого свой значок «Открыть чат» (в шапке — «Открыть чаты»).
 */
function contactChatIcon(page: Page, value: string) {
  return page
    .locator('[class*="contactItem"]')
    .filter({ hasText: value })
    .getByRole('button', { name: /^(открыть чат|open chat)$/i });
}

function wizard(page: Page) {
  return page.getByRole('dialog', {
    name: /создание нового чата|create new chat/i,
  });
}

async function contactTypeId(
  api: any,
  session: Session,
  name: string,
): Promise<number> {
  const res = await api.searchRecords(session, 'contact_type', {
    fields: ['id', 'name'],
    filter: [['name', '=', name]],
    limit: 1,
  });
  if (!res.data.length) throw new Error(`contact_type ${name} not found`);
  return res.data[0].id;
}

test.describe('Чат по значку контакта', () => {
  test.describe.configure({ mode: 'serial' });

  test.beforeAll(async ({ api, adminSession, user3Session }) => {
    const partner = await api.createRecord(adminSession, 'partners', {
      name: PARTNER_NAME,
    });
    partnerId = partner.id ?? partner.data?.id;
    const contact = await api.createRecord(adminSession, 'contact', {
      partner_id: partnerId,
      contact_type_id: await contactTypeId(api, adminSession, 'email'),
      value: PARTNER_EMAIL,
      name: PARTNER_EMAIL,
    });
    partnerContactId = contact.id ?? contact.data?.id;

    const userContact = await api.createRecord(adminSession, 'contact', {
      user_id: user3Session.user_id.id,
      contact_type_id: await contactTypeId(api, adminSession, 'telegram'),
      value: USER_TELEGRAM,
      name: USER_TELEGRAM,
    });
    userContactId = userContact.id ?? userContact.data?.id;

    // Личный чат admin ↔ user3 мог остаться от прошлых прогонов — путь
    // «чата нет» должен начинаться без него.
    const res = await api.request(
      adminSession,
      'GET',
      `/contacts/${userContactId}/chat`,
    );
    const { chat_id } = await res.json();
    if (chat_id) await api.deleteChat(adminSession, chat_id);
  });

  test.afterAll(async ({ api, adminSession }) => {
    for (const chatId of [partnerChatId, directChatId]) {
      if (chatId) await api.deleteChat(adminSession, chatId).catch(() => {});
    }
    for (const contactId of [partnerContactId, userContactId]) {
      if (contactId) {
        await api.deleteRecord(adminSession, 'contact', contactId).catch(() => {});
      }
    }
    if (partnerId) {
      await api.deleteRecord(adminSession, 'partners', partnerId).catch(() => {});
    }
  });

  test('клиент без чата: значок email → визард «Группа» с партнёром → чат клиента', async ({
    page,
    api,
    adminSession,
  }) => {
    await page.goto(`/partners/${partnerId}`);
    await contactChatIcon(page, PARTNER_EMAIL).click();

    // Визард с партнёром: тип «Группа», имя партнёра, вкладка «Партнёры».
    await expect(page).toHaveURL(/new_contact=\d+/);
    const dialog = wizard(page);
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('input[type=radio][value=group]')).toBeChecked();
    await expect(dialog.locator('input[type=radio][value=partners]')).toBeChecked();
    await expect(
      dialog.getByPlaceholder(/введите название группы|enter.*group.*name/i),
    ).toHaveValue(PARTNER_NAME);
    await expect(dialog.getByText(PARTNER_NAME).first()).toBeVisible();

    const created = page.waitForResponse(
      r => r.url().endsWith('/chats') && r.request().method() === 'POST',
    );
    await dialog.getByRole('button', { name: /^(создать|create)$/i }).click();
    expect((await created).ok()).toBeTruthy();

    // Открыт созданный чат: раздел «Клиенты», участники дочитаны.
    await expect(page).toHaveURL(/section=clients/);
    await expect(dialog).toBeHidden();
    await expect(page.getByText(/2 участник|2 members/i)).toBeVisible();

    const res = await api.request(
      adminSession,
      'GET',
      `/records/partners/${partnerId}/partner_chat`,
    );
    partnerChatId = (await res.json()).chat_id;
    expect(partnerChatId).not.toBeNull();
  });

  test('клиент с чатом: значок email открывает его сразу, с email-каналом', async ({
    page,
  }) => {
    await page.goto(`/partners/${partnerId}`);
    await contactChatIcon(page, PARTNER_EMAIL).click();

    await expect(page).toHaveURL(/section=clients/);
    await expect(wizard(page)).toHaveCount(0);
    await expect(page.getByText(/2 участник|2 members/i)).toBeVisible();
    // Канал контакта — email: у письма есть поле темы (с именем чата по
    // умолчанию), у внутреннего канала его нет.
    await expect(
      page.getByPlaceholder(/тема письма|email subject/i),
    ).toHaveValue(PARTNER_NAME);
  });

  test('сотрудник без чата: значок telegram → визард «Личный» на вкладке «Пользователи»', async ({
    page,
    api,
    adminSession,
    user3Session,
  }) => {
    const { id: user3Id, name: user3Name } = user3Session.user_id;
    await page.goto(`/users/${user3Id}`);
    await contactChatIcon(page, USER_TELEGRAM).click();

    const dialog = wizard(page);
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('input[type=radio][value=direct]')).toBeChecked();
    await expect(dialog.locator('input[type=radio][value=users]')).toBeChecked();
    await expect(dialog.getByText(user3Name).first()).toBeVisible();

    const created = page.waitForResponse(
      r => r.url().endsWith('/chats') && r.request().method() === 'POST',
    );
    await dialog.getByRole('button', { name: /^(создать|create)$/i }).click();
    expect((await created).ok()).toBeTruthy();

    await expect(page).toHaveURL(/section=staff/);
    await expect(dialog).toBeHidden();

    const res = await api.request(
      adminSession,
      'GET',
      `/contacts/${userContactId}/chat`,
    );
    directChatId = (await res.json()).chat_id;
    expect(directChatId).not.toBeNull();
  });

  test('сотрудник с чатом: значок открывает личный чат сразу', async ({
    page,
    user3Session,
  }) => {
    await page.goto(`/users/${user3Session.user_id.id}`);
    await contactChatIcon(page, USER_TELEGRAM).click();

    await expect(page).toHaveURL(/section=staff/);
    await expect(wizard(page)).toHaveCount(0);
    await expect(
      page.locator('[class*="chatArea"]').getByText(user3Session.user_id.name),
    ).toBeVisible();
  });

  test('визард: вкладка «Партнёры» — без сотрудников, поиск по имени, бейдж «есть чат» открывает чат', async ({
    page,
  }) => {
    const chat = new ChatPage(page);
    await chat.goto();
    await chat.listMenuButton.click();
    await page
      .getByRole('menuitem', { name: /^(новый чат|new chat)$/i })
      .click();
    const dialog = wizard(page);
    // Радио SegmentedControl скрыты — переключаем по подписям сегментов
    await dialog.getByText(/^(группа|group)$/i).click();
    await dialog.getByText(/^(партнёры|partners)$/i).click();

    const search = dialog.getByPlaceholder(/поиск по телефону|search by phone/i);
    // Контакт сотрудника во вкладке партнёров не показывается
    await search.fill(USER_TELEGRAM);
    await expect(page.getByRole('option')).toHaveCount(0);

    // Клиент находится по имени (contact.name — это email) и помечен
    await search.fill(PARTNER_NAME);
    const option = page.getByRole('option').filter({ hasText: PARTNER_NAME });
    await expect(option).toHaveCount(1);
    await option.getByText(/есть чат|has chat/i).click();

    await expect(page).toHaveURL(/section=clients/);
    await expect(dialog).toBeHidden();
    await expect(page.getByText(/2 участник|2 members/i)).toBeVisible();
  });

  test('визард: вкладка «Пользователи» — поиск по контакту сотрудника, бейдж «есть чат»', async ({
    page,
    user3Session,
  }) => {
    const chat = new ChatPage(page);
    await chat.goto();
    await chat.listMenuButton.click();
    await page
      .getByRole('menuitem', { name: /^(новый чат|new chat)$/i })
      .click();
    const dialog = wizard(page);

    const search = dialog.getByPlaceholder(/поиск пользователей|search users/i);
    await search.fill(USER_TELEGRAM);
    const option = page
      .getByRole('option')
      .filter({ hasText: user3Session.user_id.name });
    await expect(option).toHaveCount(1);
    await option.getByText(/есть чат|has chat/i).click();

    await expect(page).toHaveURL(/section=staff/);
    await expect(dialog).toBeHidden();
    await expect(
      page.locator('[class*="chatArea"]').getByText(user3Session.user_id.name),
    ).toBeVisible();
  });

  test('значок телефона подставляет номер в звонилку', async ({
    page,
    api,
    adminSession,
  }) => {
    const config = await (await api.request(adminSession, 'GET', '/public/config')).json();
    test.skip(!config.apps?.includes('chat_phone'), 'телефония не установлена');

    const phone = await api.createRecord(adminSession, 'contact', {
      partner_id: partnerId,
      contact_type_id: await contactTypeId(api, adminSession, 'phone'),
      value: '+79990001122',
      name: '+79990001122',
    });
    try {
      await page.goto(`/partners/${partnerId}`);
      await page
        .locator('[class*="contactItem"]')
        .filter({ hasText: '+79990001122' })
        .getByRole('button', { name: /^(набрать номер|dial number)$/i })
        .click();

      // Звонилка открыта; звонок — по её кнопке, не сразу.
      await expect(page.getByText(/чем звонить/i)).toBeVisible();
      await expect(page).toHaveURL(/\/partners\//);
    } finally {
      await api.deleteRecord(adminSession, 'contact', phone.id ?? phone.data?.id);
    }
  });
});
