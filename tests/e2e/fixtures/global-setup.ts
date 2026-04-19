/**
 * Global setup — авторизация перед запуском тестов.
 * Создаёт .auth/admin.json с cookies/storage для переиспользования.
 */
import { chromium, FullConfig } from "@playwright/test";
import { ApiHelper } from "../helpers/api.helper";
import fs from "fs";
import path from "path";

const AUTH_DIR = path.join(__dirname, "..", ".auth");
const BASE_URL = process.env.BASE_URL || "http://127.0.0.1:5173";
const API_URL = process.env.API_URL || "http://127.0.0.1:8090";
const ADMIN_LOGIN = process.env.ADMIN_LOGIN || "admin";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || "admin";
const USER2_LOGIN = process.env.USER2_LOGIN || "test1";
const USER2_PASSWORD = process.env.USER2_PASSWORD || "test1";
const USER3_LOGIN = process.env.USER3_LOGIN || "test2";
const USER3_PASSWORD = process.env.USER3_PASSWORD || "test2";

async function globalSetup(config: FullConfig) {
  // Удаляем старые auth-файлы — они могут содержать протухшие
  // сессии от предыдущего запуска (сервер перезапустился,
  // session expired, другой порт).
  if (fs.existsSync(AUTH_DIR)) {
    fs.rmSync(AUTH_DIR, { recursive: true });
  }
  fs.mkdirSync(AUTH_DIR, { recursive: true });

  const api = new ApiHelper(API_URL);
  const browser = await chromium.launch();

  // --- Admin session ---
  try {
    const adminSession = await api.login(ADMIN_LOGIN, ADMIN_PASSWORD);

    // Сбрасываем тему admin в 'modern' перед каждым прогоном тестов.
    // Это защита на случай если какой-то тест (например theme-switch)
    // упал в середине и не успел восстановить тему через try/finally.
    // Один PUT-запрос на весь прогон — дешёвая страховка.
    //
    // ВАЖНО: бэк требует ОБА header'а — Bearer token И Cookie session_cookie.
    // Без cookie возвращает 401.
    try {
      const resetRes = await fetch(
        `${API_URL}/auto/users/${adminSession.user_id.id}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${adminSession.token}`,
            Cookie: `session_cookie=${adminSession.cookieToken}`,
          },
          body: JSON.stringify({ layout_theme: "modern" }),
        },
      );
      if (!resetRes.ok) {
        console.warn(
          `⚠️ Could not reset admin layout_theme (status ${resetRes.status})`,
        );
      } else {
        // Обновляем локальный объект чтобы storageState записал modern в localStorage.
        if (adminSession.user_id) {
          (adminSession.user_id as any).layout_theme = "modern";
        }
        console.log("✅ Admin layout_theme reset to modern");
      }
    } catch (e) {
      console.warn("⚠️ Could not reset admin layout_theme:", e);
    }

    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();

    // Устанавливаем session_cookie в browser context
    const apiHost = new URL(API_URL).hostname;
    await adminContext.addCookies([
      {
        name: "session_cookie",
        value: adminSession.cookieToken,
        domain: apiHost,
        path: "/",
        httpOnly: true,
        sameSite: "Lax",
      },
    ]);

    await adminPage.goto(BASE_URL);
    await adminPage.evaluate((session) => {
      const { cookieToken, ...sessionData } = session;
      localStorage.setItem("session", JSON.stringify(sessionData));
    }, adminSession);

    // Перезагружаем чтобы app подхватил session
    await adminPage.goto(BASE_URL);
    await adminPage.waitForTimeout(2000);

    await adminContext.storageState({
      path: path.join(AUTH_DIR, "admin.json"),
    });
    await adminPage.close();
    await adminContext.close();

    console.log("✅ Admin session created");

    // --- Второй пользователь (для чат-тестов) ---
    // Автоматически создаёт test1/test1 с ролью Internal User
    try {
      // Создаём пользователя если не существует
      await api.ensureUser(adminSession, {
        login: USER2_LOGIN,
        password: USER2_PASSWORD,
        name: "Test User 1",
      });

      const user2Session = await api.login(USER2_LOGIN, USER2_PASSWORD);
      const user2Context = await browser.newContext();
      const user2Page = await user2Context.newPage();

      // Устанавливаем session_cookie в browser context
      await user2Context.addCookies([
        {
          name: "session_cookie",
          value: user2Session.cookieToken,
          domain: apiHost,
          path: "/",
          httpOnly: true,
          sameSite: "Lax",
        },
      ]);

      await user2Page.goto(BASE_URL);
      await user2Page.evaluate((session) => {
        const { cookieToken, ...sessionData } = session;
        localStorage.setItem("session", JSON.stringify(sessionData));
      }, user2Session);

      await user2Page.goto(BASE_URL);
      await user2Page.waitForTimeout(2000);

      await user2Context.storageState({
        path: path.join(AUTH_DIR, "user2.json"),
      });
      await user2Page.close();
      await user2Context.close();

      // Сохраняем флаг что user2 доступен
      fs.writeFileSync(
        path.join(AUTH_DIR, "user2.ready"),
        JSON.stringify({
          login: USER2_LOGIN,
          userId: user2Session.user_id?.id,
        }),
      );

      console.log("✅ User2 session created");
    } catch (e) {
      console.warn("⚠️ Could not create user2 session:", e);
      // Удаляем флаг если был
      try {
        fs.unlinkSync(path.join(AUTH_DIR, "user2.ready"));
      } catch {}
    }

    // --- Третий пользователь (для presence-тестов, изолирован от user2) ---
    try {
      await api.ensureUser(adminSession, {
        login: USER3_LOGIN,
        password: USER3_PASSWORD,
        name: "Test User 2",
      });

      const user3Session = await api.login(USER3_LOGIN, USER3_PASSWORD);

      fs.writeFileSync(
        path.join(AUTH_DIR, "user3.ready"),
        JSON.stringify({
          login: USER3_LOGIN,
          userId: user3Session.user_id?.id,
        }),
      );

      console.log("✅ User3 session created");
    } catch (e) {
      console.warn("⚠️ Could not create user3 session:", e);
      try {
        fs.unlinkSync(path.join(AUTH_DIR, "user3.ready"));
      } catch {}
    }
  } catch (e) {
    console.error("❌ Global setup failed:", e);
    throw e;
  }

  await browser.close();
}

export default globalSetup;
