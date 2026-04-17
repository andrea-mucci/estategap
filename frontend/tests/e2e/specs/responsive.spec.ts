import { test, expect, devices } from "@playwright/test";

import { storageStatePath } from "../fixtures/auth";

test.use({ storageState: storageStatePath("pro") });

test.describe("responsive layout", () => {
  test("mobile layout shows the sidebar toggle", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto("/en/home");
    await expect(page.getByTestId("sidebar-toggle")).toBeVisible();
    await page.getByTestId("sidebar-toggle").click();
  });

  test("tablet layout keeps the workspace shell usable", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto("/en/home");
    await expect(page.getByText(/workspace/i)).toBeVisible();
  });
});
