import { test, expect } from "@playwright/test";

import { storageStatePath } from "../fixtures/auth";
import { DashboardPage } from "../pages/DashboardPage";

test.use({ storageState: storageStatePath("pro") });

test("dashboard summary cards and charts render and country tabs switch", async ({ page }) => {
  const dashboard = new DashboardPage(page);
  await dashboard.goto();

  await expect(page.getByTestId("dashboard-summary-card-total_listings")).toBeVisible();
  await expect(page.locator("svg").first()).toBeVisible();
  const summaryRequest = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/dashboard/summary") &&
      response.url().includes("country=PT"),
  );
  await dashboard.switchCountryTab("PT");
  await summaryRequest;
  await expect(page).toHaveURL(/country=PT/);
});
