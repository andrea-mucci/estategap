import type { Page } from "@playwright/test";

export class DashboardPage {
  constructor(private readonly page: Page) {}

  async goto() {
    await this.page.goto("/en/dashboard");
  }

  getCardValue(label: string) {
    return this.page.getByTestId(`dashboard-summary-card-${label}`).textContent();
  }

  areChartsRendered() {
    return this.page.locator("svg").first().isVisible();
  }

  switchCountryTab(countryCode: string) {
    return this.page.getByRole("button", { name: new RegExp(countryCode, "i") }).click();
  }
}
