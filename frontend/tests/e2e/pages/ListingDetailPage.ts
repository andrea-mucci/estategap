import type { Page } from "@playwright/test";

export class ListingDetailPage {
  constructor(private readonly page: Page) {}

  async goto(id: string) {
    await this.page.goto(`/en/listing/${id}`);
  }

  isPhotoGalleryVisible() {
    return this.page.getByTestId("photo-gallery").isVisible();
  }

  isStatsVisible() {
    return this.page.getByTestId("stats-panel").isVisible();
  }

  isSHAPChartVisible() {
    return this.page.getByTestId("shap-chart").isVisible();
  }

  isPriceHistoryVisible() {
    return this.page.getByTestId("price-history").isVisible();
  }

  isComparablesVisible() {
    return this.page.getByTestId("comparables").isVisible();
  }

  isMapVisible() {
    return this.page.getByTestId("map-embed").isVisible();
  }

  clickTranslate() {
    return this.page.getByTestId("translate-button").click();
  }

  setCRMStatus(status: string) {
    return this.page.getByTestId(`crm-action-${status}`).click();
  }

  getCRMStatus(status: string) {
    return this.page.getByTestId(`crm-action-${status}`);
  }
}
