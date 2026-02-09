import { test, expect } from '../../fixtures';

test.describe('Переключение views', () => {
  test('theme classic ↔ modern переключается с первого клика', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Открываем UserMenu
    const userButton = page.locator('[class*="user"], [class*="User"]').filter({
      has: page.locator('img, [class*="Avatar"]'),
    }).first();
    await userButton.click();

    // Находим пункт темы
    const themeItem = page.getByText(/тема интерфейса|layout theme/i).first();
    await themeItem.click();

    // Запоминаем текущую тему
    const bodyBefore = await page.evaluate(() =>
      document.body.getAttribute('data-layout-theme'),
    );

    // Кликаем на противоположную тему
    const targetTheme = bodyBefore === 'modern' ? 'classic' : 'modern';
    const targetLabel = targetTheme === 'modern'
      ? /современ|modern/i
      : /классич|classic/i;

    await page.getByText(targetLabel).last().click();

    // Проверяем что тема сменилась
    await expect.poll(
      () => page.evaluate(() => document.body.getAttribute('data-layout-theme')),
      { timeout: 5_000 },
    ).toBe(targetTheme);
  });
});
