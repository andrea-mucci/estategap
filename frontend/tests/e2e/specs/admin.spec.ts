import { test, expect } from "@playwright/test";

import { storageStatePath } from "../fixtures/auth";
import { AdminPage } from "../pages/AdminPage";
import { LoginPage } from "../pages/LoginPage";

test.describe("admin access", () => {
  test("non-admin users are denied admin access", async ({ page }) => {
    const admin = new AdminPage(page);
    const login = new LoginPage(page);

    await login.goto();
    await login.fillEmail("free@test.estategap.com");
    await login.fillPassword("secret");
    await login.submit();
    await expect(page).toHaveURL(/\/en\/home/);

    await admin.goto();
    await expect
      .poll(async () => admin.isAccessDenied(), {
        message: "expected the admin route to resolve to an access-denied or not-found state",
      })
      .toBe(true);
  });
});

test.describe("admin workspace", () => {
  test.use({ storageState: storageStatePath("admin") });

  test("admin users can open the admin workspace", async ({ page }) => {
    const admin = new AdminPage(page);
    await admin.goto();
    await expect(page.getByRole("heading", { name: /admin panel/i })).toBeVisible();
  });
});
