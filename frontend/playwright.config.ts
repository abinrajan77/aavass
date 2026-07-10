import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for Module 1's frontend test plan
 * (specs/01-auth-rbac-tower-setup/frontend.md "Frontend test plan").
 *
 * There is no live backend in this repo state (built concurrently by
 * another agent), so every test in tests/e2e mocks
 * `NEXT_PUBLIC_API_BASE_URL` responses via Playwright's `page.route()` —
 * see tests/mocks/api.ts for the fixtures. This is documented deliberately
 * rather than silently skipped: swap the mocks for a real backend base URL
 * once Module 1's backend is live and these should keep passing unchanged
 * (they assert on rendered UI, not on mock internals).
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["html", { open: "never" }], ["list"]],
  use: {
    baseURL: "http://localhost:3100",
    trace: "on-first-retry",
  },
  webServer: {
    command: "npm run dev -- -p 3100",
    url: "http://localhost:3100/login",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: {
      NEXT_PUBLIC_API_BASE_URL: "http://localhost:3100/__mock_api__",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
