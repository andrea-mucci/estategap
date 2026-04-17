import { test, expect } from "@playwright/test";

import { storageStatePath } from "../fixtures/auth";
import { ListingDetailPage } from "../pages/ListingDetailPage";

test.use({ storageState: storageStatePath("pro") });

test("listing detail renders core sections and CRM actions persist across reload", async ({ page }) => {
  await page.goto("/en/search");
  await page.waitForResponse((response) => response.url().includes("/api/v1/listings"));
  await page.getByTestId("listing-card").first().click();

  const detail = new ListingDetailPage(page);
  await expect(page).toHaveURL(/\/en\/listing\//);
  await expect(page.getByTestId("photo-gallery")).toBeVisible();
  await expect(page.getByTestId("stats-panel")).toBeVisible();
  await expect(page.getByTestId("shap-chart")).toBeVisible();
  await expect(page.getByTestId("price-history")).toBeVisible();
  await expect(page.getByTestId("comparables")).toBeVisible();
  await expect(page.getByTestId("map-embed")).toBeVisible();

  await detail.setCRMStatus("favorite");
  await page.reload();
  await expect(detail.getCRMStatus("favorite")).toBeVisible();
});
