import type { Page } from "@playwright/test";

export async function mockGoogleOAuth(page: Page) {
  await page.route("**/api/auth/signin/google**", async (route) => {
    await route.fulfill({
      status: 302,
      headers: {
        location: "/en/home",
      },
      body: "",
    });
  });
}
