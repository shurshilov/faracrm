import { Page, Locator, expect } from '@playwright/test';

export class LoginPage {
  readonly loginInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;

  constructor(private page: Page) {
    // Mantine TextInput с label="Логин" / "Login"
    this.loginInput = page.locator('input[name="login"]');
    this.passwordInput = page.locator('input[name="password"]');
    this.submitButton = page.getByRole('button', { name: /войти|sign in/i });
  }

  async goto() {
    await this.page.goto('/');
  }

  /** Очищаем session из localStorage чтобы гарантировать показ формы логина */
  async ensureLoggedOut() {
    await this.page.evaluate(() => {
      localStorage.removeItem('session');
      localStorage.clear();
    });
    await this.page.reload();
    await this.page.waitForLoadState('domcontentloaded');
  }

  async login(login: string, password: string) {
    await this.loginInput.waitFor({ state: 'visible', timeout: 10_000 });
    await this.loginInput.fill(login);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  async expectLoggedIn() {
    await expect(this.page).not.toHaveURL(/sign-in|login/, { timeout: 10_000 });
  }

  async expectError() {
    await expect(
      this.page.getByText(/неверн|ошибк|invalid|error|failed|incorrect/i),
    ).toBeVisible({ timeout: 10_000 });
  }
}
