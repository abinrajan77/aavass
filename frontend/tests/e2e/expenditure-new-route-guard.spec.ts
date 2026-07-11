import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, LIMITED_SESSION, mockCommonListEndpoints, seedSessionCookie, TOWER_A } from "../mocks/api";

/**
 * frontend.md: "`middleware.ts` route guards: `/expenditures/new` redirects
 * flat owners away (no `MANAGE_EXPENDITURE`)." LIMITED_SESSION has
 * VIEW_TOWER_DATA + MANAGE_ASSOCIATION_MEMBERS but not MANAGE_EXPENDITURE —
 * stands in for any tower member (association member or flat owner) without
 * the permission, per specs/00-architecture-and-standards.md §5.3 (this is
 * UX-only; the backend's `require_permission("MANAGE_EXPENDITURE")` is the
 * real boundary).
 */
test("a member without MANAGE_EXPENDITURE is redirected away from /expenditures/new", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, LIMITED_SESSION);

  await page.goto(`/towers/${TOWER_A.tower_id}/expenditures/new`);

  await expect(page).toHaveURL(/\/not-authorized/);
});

test("an admin with MANAGE_EXPENDITURE can reach /expenditures/new", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.goto(`/towers/${TOWER_A.tower_id}/expenditures/new`);

  await expect(page).toHaveURL(new RegExp(`/towers/${TOWER_A.tower_id}/expenditures/new$`));
  await expect(page.getByRole("button", { name: "Record expenditure" })).toBeVisible();
});
