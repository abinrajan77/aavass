import { test, expect } from "@playwright/test";
import {
  ADMIN_SESSION,
  LIMITED_SESSION,
  MOCK_API_PREFIX,
  OWNER_SESSION,
  TOWER_A,
  mockCommonListEndpoints,
  seedSessionCookie,
} from "../mocks/api";

/**
 * specs/05-reporting-owner-portal-notifications/frontend.md §1 "Route
 * guards": middleware.ts redirects non-owners away from /my-flats and
 * non-VIEW_REPORTS users away from a tower's /reports and /notifications
 * routes. UX-only, mirroring the existing expenditure-new-route-guard.spec.ts
 * pattern for Module 4's guard.
 */
test("a non-owner (tower admin) is redirected away from /my-flats", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.goto("/my-flats");

  await expect(page).toHaveURL(/\/not-authorized/);
});

test("a flat owner can reach /my-flats", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, OWNER_SESSION);
  await page.route(`${MOCK_API_PREFIX}/owners/me/flats-summary`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ towers: [] }) })
  );

  await page.goto("/my-flats");

  await expect(page).toHaveURL(/\/my-flats$/);
});

test("a member without VIEW_REPORTS is redirected away from /towers/[towerId]/reports", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, LIMITED_SESSION);

  await page.goto(`/towers/${TOWER_A.tower_id}/reports`);

  await expect(page).toHaveURL(/\/not-authorized/);
});

test("an admin with VIEW_REPORTS can reach /towers/[towerId]/reports", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);
  await page.route(`${MOCK_API_PREFIX}/billing-cycles*`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], page: 1, page_size: 100, total: 0 }) })
  );

  await page.goto(`/towers/${TOWER_A.tower_id}/reports`);

  await expect(page).toHaveURL(new RegExp(`/towers/${TOWER_A.tower_id}/reports$`));
  await expect(page.getByRole("heading", { name: "Reports" })).toBeVisible();
});
