import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object для List/Kanban/Gantt views.
 * Работает с ViewWrapper — search, view switching, CRUD.
 */
export class ListPage {
  readonly searchToggle: Locator;
  readonly searchInput: Locator;
  readonly table: Locator;
  readonly createButton: Locator;

  constructor(
    private page: Page,
    private model: string,
  ) {
    // Tooltip label="Поиск" на ActionIcon с IconSearch
    this.searchToggle = page.getByRole('button', { name: /поиск/i }).first();
    // input с placeholder="Поиск..."
    this.searchInput = page.getByPlaceholder(/поиск/i).first();
    this.table = page.locator('table, [class*="List"], [role="grid"]').first();
    this.createButton = page.getByRole('button', { name: /создать|create|добавить|\+/i }).first();
  }

  async goto() {
    await this.page.goto(`/${this.model}`);
    await this.page.waitForLoadState('networkidle');
    // Ждём пока появится хотя бы один интерактивный элемент на странице
    await this.page.waitForTimeout(1_000);
  }

  // ==================== Search ====================

  async search(text: string) {
    // Открыть поиск если закрыт
    if (!(await this.searchInput.isVisible().catch(() => false))) {
      // Пробуем разные селекторы для кнопки поиска
      const searchBtn = this.page.locator('[class*="search"] button, button:has(svg[class*="search"]), [aria-label*="оиск"], [title*="оиск"]').first();
      if (await searchBtn.isVisible().catch(() => false)) {
        await searchBtn.click();
      } else {
        await this.searchToggle.click();
      }
    }
    await this.searchInput.waitFor({ state: 'visible', timeout: 5_000 });
    await this.searchInput.fill(text);
    // Ждём debounce + запрос
    await this.page.waitForTimeout(1_000);
  }

  async clearSearch() {
    await this.searchInput.clear();
    await this.page.waitForTimeout(1_000);
  }

  // ==================== View Switching ====================

  async switchToView(view: 'list' | 'kanban' | 'gantt') {
    const viewButtons = this.page.locator('[class*="ViewSwitcher"], [class*="viewSwitcher"]');
    const icons: Record<string, RegExp> = {
      list: /list|список|IconList/i,
      kanban: /kanban|доска|IconLayout/i,
      gantt: /gantt|график|IconChart/i,
    };
    await viewButtons.locator(`button`).filter({
      has: this.page.locator(`svg`),
    }).nth(view === 'list' ? 0 : view === 'kanban' ? 1 : 2).click();
    // Ждём перерендер
    await this.page.waitForTimeout(500);
  }

  // ==================== CRUD ====================

  async clickRow(text: string) {
    await this.table.getByText(text, { exact: false }).first().click();
  }

  async expectRowVisible(text: string) {
    await expect(
      this.table.getByText(text, { exact: false }).first(),
    ).toBeVisible({ timeout: 10_000 });
  }

  async expectRowNotVisible(text: string) {
    await expect(
      this.table.getByText(text, { exact: false }),
    ).toHaveCount(0, { timeout: 5_000 });
  }

  async getRowCount(): Promise<number> {
    return this.table.locator('tbody tr, [class*="Card"], [class*="card"]').count();
  }
}
