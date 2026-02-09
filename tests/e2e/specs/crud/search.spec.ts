import { test, expect } from "../../fixtures";
import { ListPage } from "../../pages/ListPage";

test.describe("CRUD и поиск", () => {
  /** Создать лид со всеми обязательными полями */
  async function createLead(api: any, token: string, name: string) {
    const stages = await api.searchRecords(token, "lead_stage", {
      fields: ["id"],
      limit: 1,
    });
    const users = await api.searchRecords(token, "users", {
      fields: ["id"],
      limit: 1,
    });
    const stageId = stages.data?.[0]?.id || 1;
    const userId = users.data?.[0]?.id || 1;
    return api.createRecord(token, "leads", {
      name,
      stage_id: stageId,
      user_id: userId,
      parent_id: null,
      company_id: null,
      notes: "",
      website: "",
      email: "",
      phone: "",
      mobile: "",
    });
  }

  // test('поиск фильтрует записи в List view', async ({ page, api, adminToken }) => {
  //   await createLead(api, adminToken, 'Alpha Lead Test');
  //   await createLead(api, adminToken, 'Beta Lead Test');

  //   const listPage = new ListPage(page, 'leads');
  //   await listPage.goto();

  //   await listPage.expectRowVisible('Alpha Lead Test');
  //   await listPage.expectRowVisible('Beta Lead Test');

  //   // Поиск
  //   await listPage.search('Alpha');
  //   await listPage.expectRowVisible('Alpha Lead Test');
  //   await listPage.expectRowNotVisible('Beta Lead Test');

  //   // Очистка поиска
  //   await listPage.clearSearch();
  //   await listPage.expectRowVisible('Beta Lead Test');
  // });

  // test('поиск работает в Kanban view', async ({ page, api, adminToken }) => {
  //   await createLead(api, adminToken, 'Kanban Search A');
  //   await createLead(api, adminToken, 'Kanban Search B');

  //   const listPage = new ListPage(page, 'leads');
  //   await listPage.goto();
  //   await listPage.switchToView('kanban');

  //   await listPage.search('Kanban Search A');

  //   // В kanban тоже должен фильтроваться
  //   await expect(page.getByText('Kanban Search A')).toBeVisible();
  //   await expect(page.getByText('Kanban Search B')).toHaveCount(0);
  // });

  // test('переключение views сохраняет фильтр поиска', async ({ page }) => {
  //   const listPage = new ListPage(page, 'leads');
  //   await listPage.goto();

  //   await listPage.search('test');
  //   const countBefore = await listPage.getRowCount();

  //   // Переключаемся на kanban и обратно
  //   await listPage.switchToView('kanban');
  //   await listPage.switchToView('list');

  //   // Поиск должен сохраниться
  //   const inputValue = await listPage.searchInput.inputValue();
  //   expect(inputValue).toContain('test');
  // });
});
