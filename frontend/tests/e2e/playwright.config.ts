import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: path.resolve(__dirname),
  fullyParallel: true,
  globalSetup: path.resolve(__dirname, "global-setup.ts"),
  reporter: [
    ["html"],
    ["junit", { outputFile: "../reports/e2e/playwright.xml" }],
  ],
  use: {
    baseURL: process.env.FRONTEND_URL ?? "http://localhost:3000",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      grep: /@nightly/,
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      testMatch: [
        /auth\.spec\.ts/,
        /search\.spec\.ts/,
        /listing-detail\.spec\.ts/,
      ],
      use: { ...devices["Desktop Safari"] },
    },
  ],
});
