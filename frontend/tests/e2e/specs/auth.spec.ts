import { test, expect } from "@playwright/test";

import { LandingPage } from "../pages/LandingPage";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { mockGoogleOAuth } from "../utils/mock-google-oauth";

test("landing page, registration, login, mocked google auth, and logout", async ({ page }) => {
  const landing = new LandingPage(page);
  const register = new RegisterPage(page);
  const login = new LoginPage(page);

  await landing.goto();
  expect(await landing.getLoadTime()).toBeLessThan(2000);
  await expect(landing.getPricingTiers().first()).toBeVisible();

  await landing.clickHeroCTA();
  await expect(page).toHaveURL(/\/en\/register/);

  const email = `playwright-${Date.now()}@example.test`;
  await register.fillDisplayName("Playwright User");
  await register.fillEmail(email);
  await register.fillPassword("secret12345");
  await register.submit();
  await expect(page).toHaveURL(/\/en\/home/);

  await page.getByRole("button").filter({ hasText: /playwright user|example\.test/i }).click();
  await page.getByRole("menuitem", { name: /logout/i }).click();
  await expect(page).toHaveURL(/\/en\/login/);

  await login.fillEmail("free@test.estategap.com");
  await login.fillPassword("secret");
  await login.submit();
  await expect(page).toHaveURL(/\/en\/home/);

  await mockGoogleOAuth(page);
  await page.goto("/en/login");
  await login.clickGoogleLogin();
  await expect(page).toHaveURL(/\/en\/home/);
});
