import { test, expect } from '../../fixtures';
import { ListPage } from '../../pages/ListPage';

test.describe('CRUD и поиск', () => {
  test('поиск фильтрует записи в List view', async ({ page, api, adminToken }) => {
    // Setup: создаём 2 записи с разными именами
    await api.createRecord(adminToken, 'leads', { name: 'Alpha Lead Test' });
    await api.createRecord(adminToken, 'leads', { name: 'Beta Lead Test' });

    const listPage = new ListPage(page, 'leads');
    await listPage.goto();

    await listPage.expectRowVisible('Alpha Lead Test');
    await listPage.expectRowVisible('Beta Lead Test');

    // Поиск
    await listPage.search('Alpha');
    await listPage.expectRowVisible('Alpha Lead Test');
    await listPage.expectRowNotVisible('Beta Lead Test');

    // Очистка поиска
    await listPage.clearSearch();
    await listPage.expectRowVisible('Beta Lead Test');
  });

  test('поиск работает в Kanban view', async ({ page, api, adminToken }) => {
    await api.createRecord(adminToken, 'leads', { name: 'Kanban Search A' });
    await api.createRecord(adminToken, 'leads', { name: 'Kanban Search B' });

    const listPage = new ListPage(page, 'leads');
    await listPage.goto();
    await listPage.switchToView('kanban');

    await listPage.search('Kanban Search A');

    // В kanban тоже должен фильтроваться
    await expect(page.getByText('Kanban Search A')).toBeVisible();
    await expect(page.getByText('Kanban Search B')).toHaveCount(0);
  });

  test('переключение views сохраняет фильтр поиска', async ({ page }) => {
    const listPage = new ListPage(page, 'leads');
    await listPage.goto();

    await listPage.search('test');
    const countBefore = await listPage.getRowCount();

    // Переключаемся на kanban и обратно
    await listPage.switchToView('kanban');
    await listPage.switchToView('list');

    // Поиск должен сохраниться
    const inputValue = await listPage.searchInput.inputValue();
    expect(inputValue).toContain('test');
  });
});
