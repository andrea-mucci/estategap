import { test, expect } from "@playwright/test";

import { storageStatePath } from "../fixtures/auth";
import { ChatPage } from "../pages/ChatPage";

test.describe("visual regression", () => {
  test("captures the public landing page", async ({ page }) => {
    await page.goto("/en");
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveScreenshot("landing-page.png", { maxDiffPixelRatio: 0.001 });
  });

  test.use({ storageState: storageStatePath("pro") });

  test("captures logged-in home and dashboard pages", async ({ page }) => {
    for (const [route, name] of [
      ["/en/home", "home-authenticated.png"],
      ["/en/dashboard", "dashboard.png"],
    ] as const) {
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      await expect(page).toHaveScreenshot(name, { maxDiffPixelRatio: 0.001 });
    }
  });

  test("captures the seeded listing detail page", async ({ page }) => {
    await page.goto("/en/search");
    await page.waitForResponse((response) => response.url().includes("/api/v1/listings"));
    await page.getByTestId("listing-card").first().click();
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveScreenshot("listing-detail.png", { maxDiffPixelRatio: 0.001 });
  });

  test("captures the AI chat page mid-conversation", async ({ page }) => {
    const chat = new ChatPage(page);

    await chat.goto();
    await page.waitForLoadState("networkidle");
    await chat.sendMessage("Find me a two bedroom apartment in Madrid under 400000 EUR");
    await page.getByTestId("chat-message-assistant").last().waitFor({ timeout: 20_000 });
    await expect(page).toHaveScreenshot("ai-chat-mid-conversation.png", {
      maxDiffPixelRatio: 0.001,
    });
  });
});
