import { test, expect } from "@playwright/test";

import { storageStatePath } from "../fixtures/auth";
import { AlertsPage } from "../pages/AlertsPage";

test.use({ storageState: storageStatePath("pro") });

test("alerts form accepts prefilled values and saves a draft", async ({ page }) => {
  const alerts = new AlertsPage(page);
  await page.goto("/en/alerts?country=ES&maxPrice=450000&minArea=80&propertyType=apartment");
  await expect(page.getByLabel(/price range/i)).toHaveValue("450000");
  await alerts.createRule({ maxPrice: "450000", minArea: "80" });
});
