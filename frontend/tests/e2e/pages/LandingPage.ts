import { expect, type Page } from "@playwright/test";

export class LandingPage {
  constructor(private readonly page: Page) {}

  async goto() {
    await this.page.goto("/en");
  }

  clickHeroCTA() {
    return this.page.getByTestId("hero-primary-cta").click();
  }

  getPricingTiers() {
    return this.page.locator("#pricing table tbody tr, #pricing article");
  }

  async getLoadTime() {
    return this.page.evaluate(() =>
      performance.getEntriesByType("navigation")[0]?.duration ?? 0,
    );
  }
}
