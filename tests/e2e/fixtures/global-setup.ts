/**
 * Global setup — авторизация перед запуском тестов.
 * Создаёт .auth/admin.json с cookies/storage для переиспользования.
 */
import { chromium, FullConfig } from '@playwright/test';
import { ApiHelper } from '../helpers/api.helper';
import fs from 'fs';
import path from 'path';

const AUTH_DIR = path.join(__dirname, '..', '.auth');
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const API_URL = process.env.API_URL || 'http://localhost:8090';
const ADMIN_LOGIN = process.env.ADMIN_LOGIN || 'admin';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'admin';
const USER2_LOGIN = process.env.USER2_LOGIN || 'test1';
const USER2_PASSWORD = process.env.USER2_PASSWORD || 'test1';
const USER3_LOGIN = process.env.USER3_LOGIN || 'test2';
const USER3_PASSWORD = process.env.USER3_PASSWORD || 'test2';

async function globalSetup(config: FullConfig) {
  // Убедимся что директория существует
  fs.mkdirSync(AUTH_DIR, { recursive: true });

  const api = new ApiHelper(API_URL);
  const browser = await chromium.launch();

  // --- Admin session ---
  try {
    const adminSession = await api.login(ADMIN_LOGIN, ADMIN_PASSWORD);

    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();

    await adminPage.goto(BASE_URL);
    await adminPage.evaluate((session) => {
      localStorage.setItem('session', JSON.stringify(session));
    }, adminSession);

    // Перезагружаем чтобы app подхватил session
    await adminPage.goto(BASE_URL);
    await adminPage.waitForTimeout(2000);

    await adminContext.storageState({
      path: path.join(AUTH_DIR, 'admin.json'),
    });
    await adminPage.close();
    await adminContext.close();

    console.log('✅ Admin session created');

    // --- Второй пользователь (для чат-тестов) ---
    // Автоматически создаёт test1/test1 с ролью Internal User
    try {
      // Создаём пользователя если не существует
      await api.ensureUser(adminSession.token, {
        login: USER2_LOGIN,
        password: USER2_PASSWORD,
        name: 'Test User 1',
      });

      const user2Session = await api.login(USER2_LOGIN, USER2_PASSWORD);
      const user2Context = await browser.newContext();
      const user2Page = await user2Context.newPage();

      await user2Page.goto(BASE_URL);
      await user2Page.evaluate((session) => {
        localStorage.setItem('session', JSON.stringify(session));
      }, user2Session);

      await user2Page.goto(BASE_URL);
      await user2Page.waitForTimeout(2000);

      await user2Context.storageState({
        path: path.join(AUTH_DIR, 'user2.json'),
      });
      await user2Page.close();
      await user2Context.close();

      // Сохраняем флаг что user2 доступен
      fs.writeFileSync(
        path.join(AUTH_DIR, 'user2.ready'),
        JSON.stringify({ login: USER2_LOGIN, userId: user2Session.user_id?.id }),
      );

      console.log('✅ User2 session created');
    } catch (e) {
      console.warn('⚠️ Could not create user2 session:', e);
      // Удаляем флаг если был
      try { fs.unlinkSync(path.join(AUTH_DIR, 'user2.ready')); } catch {}
    }

    // --- Третий пользователь (для presence-тестов, изолирован от user2) ---
    try {
      await api.ensureUser(adminSession.token, {
        login: USER3_LOGIN,
        password: USER3_PASSWORD,
        name: 'Test User 2',
      });

      const user3Session = await api.login(USER3_LOGIN, USER3_PASSWORD);

      fs.writeFileSync(
        path.join(AUTH_DIR, 'user3.ready'),
        JSON.stringify({ login: USER3_LOGIN, userId: user3Session.user_id?.id }),
      );

      console.log('✅ User3 session created');
    } catch (e) {
      console.warn('⚠️ Could not create user3 session:', e);
      try { fs.unlinkSync(path.join(AUTH_DIR, 'user3.ready')); } catch {}
    }
  } catch (e) {
    console.error('❌ Global setup failed:', e);
    throw e;
  }

  await browser.close();
}

export default globalSetup;
