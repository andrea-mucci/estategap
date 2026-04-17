import type { Page } from "@playwright/test";

export class AdminPage {
  constructor(private readonly page: Page) {}

  async goto() {
    await this.page.goto("/en/admin");
  }

  isAccessDenied() {
    return this.page
      .locator("body")
      .textContent()
      .then((text) => /admin access required|page could not be found/i.test(text ?? ""));
  }

  getScrapingStats() {
    return this.page.getByRole("heading", { name: /admin panel/i }).isVisible();
  }

  async clickRetrain() {
    const button = this.page.getByRole("button", { name: /retrain/i }).first();
    if (await button.isVisible()) {
      await button.click();
    }
  }

  getUserListRows() {
    return this.page.locator("table tbody tr");
  }
}
