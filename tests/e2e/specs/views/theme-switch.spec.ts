import { test, expect, Page } from '../../fixtures';

/**
 * Переключает тему через UserMenu до target. Если тема уже такая — no-op.
 * Читает `data-layout-theme` с body как источник правды.
 */
async function switchThemeTo(page: Page, target: 'classic' | 'modern') {
  const current = await page.evaluate(() =>
    document.body.getAttribute('data-layout-theme'),
  );
  if (current === target) return;

  await page.locator('button:has-text("Administrator")').last().click();
  await page.waitForTimeout(300);

  await page.getByText(/тема интерфейса|layout theme/i).first().click();
  await page.waitForTimeout(500);

  const targetLabel =
    target === 'modern' ? /современ|modern/i : /классич|classic/i;
  const themeOption = page.getByText(targetLabel).last();
  await themeOption.waitFor({ state: 'visible', timeout: 5_000 });
  await themeOption.click();

  await expect
    .poll(
      () =>
        page.evaluate(() =>
          document.body.getAttribute('data-layout-theme'),
        ),
      { timeout: 5_000 },
    )
    .toBe(target);
}

test.describe('Переключение views', () => {
  test('theme classic ↔ modern переключается с первого клика', async ({
    page,
  }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Нормализуем начальное состояние — всегда стартуем с 'modern',
    // чтобы тест не зависел от того, в каком состоянии БД.
    await switchThemeTo(page, 'modern');

    try {
      // Проверяем что переключение на classic работает с первого клика.
      await switchThemeTo(page, 'classic');
      expect(
        await page.evaluate(() =>
          document.body.getAttribute('data-layout-theme'),
        ),
      ).toBe('classic');

      // И обратно.
      await switchThemeTo(page, 'modern');
      expect(
        await page.evaluate(() =>
          document.body.getAttribute('data-layout-theme'),
        ),
      ).toBe('modern');
    } finally {
      // CLEANUP: независимо от результата теста, оставляем БД в 'modern'.
      // Без этого admin в БД остался бы с 'classic' и следующие сессии
      // открывались бы с classic-темой.
      try {
        await switchThemeTo(page, 'modern');
      } catch (e) {
        console.warn('theme-switch cleanup failed:', e);
      }
    }
  });
});
