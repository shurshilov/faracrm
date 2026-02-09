const ADMIN_LOGIN = process.env.ADMIN_LOGIN || 'admin';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'admin';

import { test, expect } from '../../fixtures';
import { LoginPage } from '../../pages/LoginPage';

test.describe('Авторизация', () => {
  // Эти тесты используют чистый контекст без storageState
  test.use({ storageState: undefined });

  test('успешный логин admin', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(ADMIN_LOGIN, ADMIN_PASSWORD);
    await loginPage.expectLoggedIn();
  });

  test('неверный пароль показывает ошибку', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login('admin', 'wrongpassword');
    await loginPage.expectError();
  });

  test('пустой логин — кнопка неактивна или ошибка валидации', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login('', '');
    // Остаёмся на странице логина
    await expect(page.getByRole('button', { name: /войти|sign in/i })).toBeVisible();
  });

  test('после логина доступны страницы приложения', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(ADMIN_LOGIN, ADMIN_PASSWORD);
    await loginPage.expectLoggedIn();

    // Проверяем что sidebar или header загружен
    await expect(
      page.locator('[class*="header"], [class*="sidebar"], [class*="Layout"]').first(),
    ).toBeVisible();
  });
});
