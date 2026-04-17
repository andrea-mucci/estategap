import { test, expect } from "@playwright/test";

import { storageStatePath } from "../fixtures/auth";

test.use({ storageState: storageStatePath("pro") });

test("dashboard map renders with the draw zone control", async ({ page }) => {
  await page.goto("/en/dashboard");
  await expect(page.getByTestId("map-container")).toBeVisible();
  await expect(page.getByRole("button", { name: /draw zone/i })).toBeVisible();
});
