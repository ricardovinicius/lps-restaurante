import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 45000,
  expect: { timeout: 10000 },
  use: {
    ...devices["Desktop Chrome"],
    baseURL: process.env.MESA_BASE_URL ?? "http://127.0.0.1:8080",
    trace: "retain-on-failure",
    launchOptions: process.env.MESA_BROWSER_PATH ? { executablePath: process.env.MESA_BROWSER_PATH } : {},
  },
});
