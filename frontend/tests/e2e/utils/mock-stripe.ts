import type { Page } from "@playwright/test";

export async function mockStripeCheckout(page: Page) {
  await page.route("**/api/v1/subscriptions/checkout", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        checkout_url: "https://checkout.stripe.com/c/pay/cs_test_mock",
      }),
    });
  });

  await page.route("https://checkout.stripe.com/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<html><body>Mock Stripe Checkout</body></html>",
    });
  });
}
