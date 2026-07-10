import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

/**
 * Component-test runner for Module 3's frontend test plan
 * (specs/03-maintenance-billing/frontend.md §4.1). No component-test tooling
 * existed anywhere in this repo before this module (only Playwright e2e,
 * see playwright.config.ts) — Vitest + React Testing Library is added here
 * as the minimal, standard choice for a Next.js/shadcn app, scoped to
 * `tests/component/**` so it never touches the e2e suite.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
    include: ["tests/component/**/*.test.{ts,tsx}"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
