import fs from "node:fs";
import path from "node:path";

import { chromium, type FullConfig } from "@playwright/test";

import { TIER_USERS, type Tier } from "./fixtures/users";

const AUTH_DIR = path.resolve(__dirname, "auth");

async function ensureAdminUser(apiBaseUrl: string) {
  await fetch(`${apiBaseUrl}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: TIER_USERS.admin.email,
      password: TIER_USERS.admin.password,
      display_name: "EstateGap Admin",
    }),
  }).catch(() => undefined);
}

export default async function globalSetup(config: FullConfig) {
  fs.mkdirSync(AUTH_DIR, { recursive: true });

  const baseURL = config.projects[0]?.use?.baseURL ?? "http://localhost:3000";
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
  await ensureAdminUser(apiBaseUrl);

  const browser = await chromium.launch();
  try {
    for (const tier of Object.keys(TIER_USERS) as Tier[]) {
      const page = await browser.newPage();
      await page.goto(`${baseURL}/en/login`);
      await page.getByLabel("Email").fill(TIER_USERS[tier].email);
      await page.getByLabel("Password").fill(TIER_USERS[tier].password);
      await page.getByRole("button", { name: /sign in|login/i }).click();
      await page.waitForURL(/\/en\/home/, { timeout: 20_000 });
      await page.context().storageState({ path: path.join(AUTH_DIR, `${tier}.json`) });
      await page.close();
    }
  } finally {
    await browser.close();
  }
}
