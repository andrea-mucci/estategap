import type { Page } from "@playwright/test";

export class RegisterPage {
  constructor(private readonly page: Page) {}

  async goto() {
    await this.page.goto("/en/register");
  }

  fillDisplayName(value: string) {
    return this.page.getByLabel("Name").fill(value);
  }

  fillEmail(value: string) {
    return this.page.getByLabel("Email").fill(value);
  }

  fillPassword(value: string) {
    return this.page.getByLabel("Password").fill(value);
  }

  submit() {
    return this.page.getByRole("button", { name: /create|register/i }).click();
  }

  getErrorMessage() {
    return this.page.getByText(/error/i);
  }
}
