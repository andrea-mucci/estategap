import fs from "node:fs";
import path from "node:path";

import { expect, type Page, test as base } from "@playwright/test";

import { TIER_USERS, type Tier } from "./users";

const AUTH_DIR = path.resolve(__dirname, "../auth");

export function storageStatePath(tier: Tier) {
  return path.join(AUTH_DIR, `${tier}.json`);
}

export async function loginAs(page: Page, tier: Tier) {
  const creds = TIER_USERS[tier];
  await page.goto("/en/login");
  await page.getByLabel("Email").fill(creds.email);
  await page.getByLabel("Password").fill(creds.password);
  await page.getByRole("button", { name: /sign in|login/i }).click();
  await page.waitForURL(/\/en\/home/, { timeout: 20_000 });
}

type AuthFixtures = {
  tier: Tier;
};

export function createTieredTest(tier: Tier) {
  return base.extend<AuthFixtures>({
    storageState: async ({}, use) => {
      const storagePath = storageStatePath(tier);
      await use(fs.existsSync(storagePath) ? storagePath : undefined);
    },
    tier: async ({}, use) => {
      await use(tier);
    },
  });
}

export { expect };
