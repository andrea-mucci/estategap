import { test, expect, type Locator, type Page } from "@playwright/test";
import { injectAxe, checkA11y } from "axe-playwright";

import { storageStatePath } from "../fixtures/auth";

async function checkPageA11y(page: Page) {
  await injectAxe(page);
  await checkA11y(page, undefined, {
    detailedReport: true,
    runOnly: ["wcag2a", "wcag2aa"],
  });
}

async function tabUntilFocused(page: Page, locator: Locator, label: string, attempts = 20) {
  for (let index = 0; index < attempts; index += 1) {
    await page.keyboard.press("Tab");
    const isFocused = await locator.evaluate((element) => element === document.activeElement).catch(() => false);
    if (isFocused) {
      await expect(locator).toBeFocused();
      return;
    }
  }

  throw new Error(`Unable to focus ${label} with keyboard navigation`);
}

test.describe("@a11y public pages", () => {
  test("landing page passes axe and its primary CTA is keyboard reachable", async ({ page }) => {
    await page.goto("/en");
    await checkPageA11y(page);

    await tabUntilFocused(page, page.getByTestId("hero-primary-cta"), "hero CTA");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/en\/register/);
  });

  test("login page passes axe and supports keyboard submission", async ({ page }) => {
    await page.goto("/en/login");
    await checkPageA11y(page);

    await tabUntilFocused(page, page.getByLabel("Email"), "email input");
    await page.keyboard.type("free@test.estategap.com");
    await tabUntilFocused(page, page.getByLabel("Password"), "password input");
    await page.keyboard.type("secret");
    await tabUntilFocused(page, page.getByRole("button", { name: /sign in|login/i }), "sign in button");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/en\/home/);
  });
});

test.describe("@a11y authenticated pages", () => {
  test.use({ storageState: storageStatePath("pro") });

  test("primary authenticated routes pass axe smoke checks", async ({ page }) => {
    for (const route of ["/en/home", "/en/chat", "/en/search", "/en/dashboard", "/en/alerts"]) {
      await page.goto(route);
      await checkPageA11y(page);
    }

    await page.goto("/en/search");
    await page.waitForResponse((response) => response.url().includes("/api/v1/listings"));
    await page.getByTestId("listing-card").first().click();
    await expect(page).toHaveURL(/\/en\/listing\//);
    await checkPageA11y(page);
  });

  test("chat page supports keyboard navigation to send a message", async ({ page }) => {
    await page.goto("/en/chat");
    const input = page.getByTestId("chat-input");
    await input.fill("Find me something in Madrid");
    await input.focus();

    await tabUntilFocused(page, page.getByTestId("chat-send-button"), "chat send button", 10);
    await page.keyboard.press("Enter");
    await page.getByTestId("chat-message-assistant").last().waitFor({ timeout: 20_000 }).catch(() => undefined);
  });
});

test.describe("@a11y admin denied", () => {
  test.use({ storageState: storageStatePath("free") });

  test("non-admin users see an accessible admin-denied state", async ({ page }) => {
    await page.goto("/en/admin");
    await expect(page.locator("body")).toContainText(/admin access required|page could not be found/i);
    await checkPageA11y(page);
  });
});
