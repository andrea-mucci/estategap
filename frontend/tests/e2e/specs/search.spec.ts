import { test, expect } from "@playwright/test";

import { storageStatePath } from "../fixtures/auth";
import { SearchPage } from "../pages/SearchPage";

test.use({ storageState: storageStatePath("pro") });

test("search updates params, toggles views, and saves a search", async ({ page }) => {
  const search = new SearchPage(page);
  await search.goto();

  await page.waitForResponse((response) => response.url().includes("/api/v1/listings"));
  await search.setFilter("country", "ES");
  await expect(page).toHaveURL(/country=ES/);

  await search.setSortOrder("price:asc");
  await expect(page).toHaveURL(/sort_by=price/);

  await search.toggleListView();
  await expect(page.getByTestId("search-results-list")).toBeVisible();
  await search.toggleGridView();
  await expect(page.getByTestId("search-results-grid")).toBeVisible();

  await search.saveSearch("Playwright Search");
  await search.deleteSavedSearch("Playwright Search");
});
