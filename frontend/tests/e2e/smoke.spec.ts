import { test, expect } from "@playwright/test";

test("login page renders the core form elements", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("Aavaas", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
});

test("unauthenticated request to a protected route redirects to /login", async ({ page }) => {
  await page.goto("/towers/tower-a");
  await expect(page).toHaveURL(/\/login/);
});
