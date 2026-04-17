import { test, expect } from "@playwright/test";

import { storageStatePath } from "../fixtures/auth";
import { SubscriptionPage } from "../pages/SubscriptionPage";

test.use({ storageState: storageStatePath("free") });

test("pricing CTA routes users into the upgrade/register flow", async ({ page }) => {
  const subscription = new SubscriptionPage(page);
  await subscription.goto();
  await subscription.clickUpgrade("pro");
  await expect(page).toHaveURL(/\/en\/register/);
});
