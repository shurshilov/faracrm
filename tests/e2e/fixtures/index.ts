/**
 * Расширенные fixtures для FARA CRM тестов.
 *
 * Использование:
 *   import { test, expect } from '../fixtures';
 *   test('...', async ({ adminPage, api, adminToken }) => { ... });
 */
import { test as base, expect, Page, BrowserContext } from '@playwright/test';
import { ApiHelper, Session } from '../helpers/api.helper';
import { WSClient } from '../helpers/ws.helper';
import path from 'path';

const API_URL = process.env.API_URL || 'http://localhost:8090';
const WS_URL = (process.env.API_URL || 'http://localhost:8090').replace('http', 'ws');
const ADMIN_LOGIN = process.env.ADMIN_LOGIN || 'admin';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'admin';
const USER2_LOGIN = process.env.USER2_LOGIN || 'test1';
const USER2_PASSWORD = process.env.USER2_PASSWORD || 'test1';
const USER3_LOGIN = process.env.USER3_LOGIN || 'test2';
const USER3_PASSWORD = process.env.USER3_PASSWORD || 'test2';

// Кэш сессий чтобы не логиниться каждый тест
let adminSessionCache: Session | null = null;
let user2SessionCache: Session | null = null;
let user3SessionCache: Session | null = null;

type TestFixtures = {
  /** API helper для подготовки данных */
  api: ApiHelper;

  /** Токен admin */
  adminToken: string;
  /** Сессия admin */
  adminSession: Session;

  /** Токен второго пользователя */
  user2Token: string;
  /** Сессия второго пользователя */
  user2Session: Session;

  /** Страница залогиненная как user2 (для multi-user тестов) */
  user2Page: Page;
  /** Browser context для user2 */
  user2Context: BrowserContext;

  /** WS клиент для admin */
  adminWS: WSClient;
  /** WS клиент для user2 */
  user2WS: WSClient;

  /** Токен третьего пользователя (для presence-тестов) */
  user3Token: string;
  /** Сессия третьего пользователя */
  user3Session: Session;
  /** WS клиент для user3 */
  user3WS: WSClient;
};

export const test = base.extend<TestFixtures>({
  api: async ({}, use) => {
    await use(new ApiHelper(API_URL));
  },

  adminSession: async ({ api }, use) => {
    if (!adminSessionCache) {
      adminSessionCache = await api.login(ADMIN_LOGIN, ADMIN_PASSWORD);
    }
    await use(adminSessionCache);
  },

  adminToken: async ({ adminSession }, use) => {
    await use(adminSession.token);
  },

  user2Session: async ({ api }, use) => {
    if (!user2SessionCache) {
      try {
        user2SessionCache = await api.login(USER2_LOGIN, USER2_PASSWORD);
      } catch (e) {
        console.warn('User2 login failed, multi-user tests will fail:', e);
        await use(null as any);
        return;
      }
    }
    await use(user2SessionCache);
  },

  user2Token: async ({ user2Session }, use) => {
    await use(user2Session?.token || '');
  },

  user2Context: async ({ browser }, use) => {
    const authFile = path.join(__dirname, '..', '.auth', 'user2.json');
    const context = await browser.newContext({ storageState: authFile });
    await use(context);
    await context.close();
  },

  user2Page: async ({ user2Context }, use) => {
    const page = await user2Context.newPage();
    await use(page);
    await page.close();
  },

  adminWS: async ({ adminToken }, use) => {
    const ws = new WSClient(WS_URL, adminToken);
    await ws.connect();
    await use(ws);
    await ws.close();
  },

  user2WS: async ({ user2Token }, use) => {
    const ws = new WSClient(WS_URL, user2Token);
    await ws.connect();
    await use(ws);
    await ws.close();
  },

  user3Session: async ({ api }, use) => {
    if (!user3SessionCache) {
      try {
        user3SessionCache = await api.login(USER3_LOGIN, USER3_PASSWORD);
      } catch (e) {
        console.warn('User3 login failed, presence tests will fail:', e);
        await use(null as any);
        return;
      }
    }
    await use(user3SessionCache);
  },

  user3Token: async ({ user3Session }, use) => {
    await use(user3Session?.token || '');
  },

  user3WS: async ({ user3Token }, use) => {
    const ws = new WSClient(WS_URL, user3Token);
    await ws.connect();
    await use(ws);
    await ws.close();
  },
});

export { expect };
