import type { Page } from "@playwright/test";

export class AlertsPage {
  constructor(private readonly page: Page) {}

  async goto() {
    await this.page.goto("/en/alerts");
  }

  async createRule(params: { country?: string; maxPrice?: string; minArea?: string }) {
    if (params.country) {
      await this.page.getByLabel(/country/i).selectOption(params.country);
    }
    if (params.maxPrice) {
      await this.page.getByLabel(/price range/i).fill(params.maxPrice);
    }
    if (params.minArea) {
      await this.page.getByLabel(/area range/i).fill(params.minArea);
    }
    await this.page.getByRole("button", { name: /save/i }).click();
  }

  editRule() {
    return Promise.resolve();
  }

  deleteRule() {
    return Promise.resolve();
  }

  getHistoryEntries() {
    return this.page.locator("table tbody tr");
  }
}
