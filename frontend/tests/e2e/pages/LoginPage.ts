import type { Page } from "@playwright/test";

export class LoginPage {
  constructor(private readonly page: Page) {}

  async goto() {
    await this.page.goto("/en/login");
  }

  fillEmail(email: string) {
    return this.page.getByLabel("Email").fill(email);
  }

  fillPassword(password: string) {
    return this.page.getByLabel("Password").fill(password);
  }

  submit() {
    return this.page.getByRole("button", { name: /sign in|login/i }).click();
  }

  clickGoogleLogin() {
    return this.page.getByRole("button", { name: /google/i }).click();
  }

  getErrorMessage() {
    return this.page.getByText(/invalid|error/i);
  }
}
