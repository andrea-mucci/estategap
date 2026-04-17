import type { Page } from "@playwright/test";

export class SubscriptionPage {
  constructor(private readonly page: Page) {}

  async goto() {
    await this.page.goto("/en");
  }

  isUpgradePromptVisible() {
    return this.page.getByText(/upgrade/i).isVisible();
  }

  clickUpgrade(_tier: string) {
    return this.page.getByTestId("hero-primary-cta").click();
  }

  waitForStripeRedirect() {
    return this.page.waitForURL(/register|stripe/i);
  }
}
