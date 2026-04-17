import type { Page } from "@playwright/test";

export class SearchPage {
  constructor(private readonly page: Page) {}

  async goto() {
    await this.page.goto("/en/search");
  }

  async setFilter(name: string, value: string) {
    await this.page.locator(`select`).nth(name === "country" ? 0 : 1).selectOption(value);
  }

  async getURLSearchParams() {
    return new URL(this.page.url()).searchParams;
  }

  getResultCount() {
    return this.page.getByTestId("search-results-count").textContent();
  }

  async setSortOrder(value: string) {
    await this.page.getByLabel(/sort/i).selectOption(value);
  }

  toggleGridView() {
    return this.page.getByLabel(/grid/i).click();
  }

  toggleListView() {
    return this.page.getByLabel(/list/i).click();
  }

  async saveSearch(name: string) {
    await this.page.getByTestId("save-search-button").click();
    await this.page.getByTestId("save-search-name").fill(name);
    await this.page.getByTestId("save-search-confirm").click();
  }

  async deleteSavedSearch(_name: string) {
    await this.page.getByTestId("saved-searches-button").click();
    await this.page.getByTestId("saved-search-delete").first().click();
  }
}
