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
      this.page.getByText(/неверн|ошибк|invalid|error|failed/i),
    ).toBeVisible({ timeout: 5_000 });
  }
}
