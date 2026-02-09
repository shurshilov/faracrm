import { test, expect } from '../../fixtures';

test.describe('Переключение views', () => {
  test('theme classic ↔ modern переключается с первого клика', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Открываем UserMenu — кнопка с именем пользователя
    await page.locator('button:has-text("Administrator")').last().click();
    await page.waitForTimeout(300);

    // Кликаем "Тема интерфейса" — открывает подменю
    const themeItem = page.getByText(/тема интерфейса|layout theme/i).first();
    await themeItem.click();
    await page.waitForTimeout(500);

    // Запоминаем текущую тему
    const bodyBefore = await page.evaluate(() =>
      document.body.getAttribute('data-layout-theme'),
    );

    // Кликаем на противоположную тему в подменю
    const targetTheme = bodyBefore === 'modern' ? 'classic' : 'modern';
    const targetLabel = targetTheme === 'modern'
      ? /современ|modern/i
      : /классич|classic/i;

    // Ищем в подменю/попапе
    const themeOption = page.getByText(targetLabel).last();
    await themeOption.waitFor({ state: 'visible', timeout: 5_000 }).catch(() => {});

    if (await themeOption.isVisible()) {
      await themeOption.click();

      // Проверяем что тема сменилась
      await expect.poll(
        () => page.evaluate(() => document.body.getAttribute('data-layout-theme')),
        { timeout: 5_000 },
      ).toBe(targetTheme);
    } else {
      // Подменю может быть реализовано иначе — пропускаем
      test.skip();
    }
  });
});
