import path from "node:path";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

/**
 * Vitest + React Testing Library config for the "Component tests (Vitest/RTL)"
 * plan in specs/04-special-collections-expenditure/frontend.md (this is the
 * first module to add component-level tests to this repo — Module 1 only had
 * Playwright e2e; see tests/component/README notes in each spec file for
 * why). Playwright's own config/tests are untouched (playwright.config.ts,
 * tests/e2e/**) — this only covers tests/component/**.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    css: false,
    setupFiles: ["./tests/setup/vitest-setup.ts"],
    include: ["tests/component/**/*.test.{ts,tsx}"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
