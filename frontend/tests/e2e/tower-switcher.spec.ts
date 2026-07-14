import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, TOWER_A, TOWER_B, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";

/**
 * specs/01-auth-rbac-tower-setup/frontend.md frontend test plan:
 * "A tower admin with two tower memberships uses the Command tower-switcher
 * to move from Tower A's shell to Tower B's shell, and the URL/breadcrumb/nav
 * all update to Tower B's context with no stale Tower-A data flashing."
 */
test("tower switcher (Ctrl+K) moves context from Tower A to Tower B with no stale data", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.goto(`/towers/${TOWER_A.tower_id}`);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByText(TOWER_A.tower_name, { exact: true })).toBeVisible();

  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByText(TOWER_B.tower_name).click();

  await expect(page).toHaveURL(new RegExp(`/towers/${TOWER_B.tower_id}$`));
  // The breadcrumb re-renders with the new tower's name — asserting the old
  // tower's name is gone confirms no stale Tower-A content.
  await expect(page.getByText(TOWER_B.tower_name, { exact: true })).toBeVisible();
  await expect(page.getByText(TOWER_A.tower_name, { exact: true })).toHaveCount(0);
});
