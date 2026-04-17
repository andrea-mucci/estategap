import { test, expect } from "@playwright/test";

import { storageStatePath } from "../fixtures/auth";

test.describe("visual regression", () => {
  test("captures the public landing page", async ({ page }) => {
    await page.goto("/en");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveScreenshot("landing-page.png", { maxDiffPixelRatio: 0.001 });
  });

  test.use({ storageState: storageStatePath("pro") });

  test("captures logged-in core pages", async ({ page }) => {
    for (const [route, name] of [
      ["/en/home", "home-authenticated.png"],
      ["/en/dashboard", "dashboard.png"],
      ["/en/search", "search.png"],
      ["/en/alerts", "alerts.png"],
    ] as const) {
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      await expect(page).toHaveScreenshot(name, { maxDiffPixelRatio: 0.001 });
    }
  });
});
