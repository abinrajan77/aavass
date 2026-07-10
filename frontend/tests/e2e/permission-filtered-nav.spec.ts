import { test, expect } from "@playwright/test";
import { LIMITED_SESSION, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";

/**
 * specs/01-auth-rbac-tower-setup/frontend.md frontend test plan:
 * "Login → dashboard renders only nav items in the Sidebar corresponding to
 * the logged-in user's granted permissions ... a member without
 * MANAGE_EXPENDITURE never sees an 'Expenditures' nav link" and the "must
 * NOT break" rule that nav derives from session.permissions, never a
 * hardcoded role check.
 *
 * LIMITED_SESSION only grants VIEW_TOWER_DATA + MANAGE_ASSOCIATION_MEMBERS,
 * so Dashboard/Association Members/Roles should render but Tower Profile
 * (gated on MANAGE_COMPLEX) must not.
 */
test("nav is filtered by session.permissions, not a role name", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, LIMITED_SESSION);

  await page.goto("/towers/tower-a");

  await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Association Members" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Roles" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Tower Profile" })).toHaveCount(0);
});
