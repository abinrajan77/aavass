import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, TOWER_A, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";

/**
 * specs/02-flat-owner-tenant/frontend.md frontend test plan:
 * "Occupancy Badge renders the correct variant/token for each of the three
 * statuses and never reuses success/warning/destructive."
 *
 * Renders the flats DataTable with one flat per occupancy_status and
 * asserts both the visible label and, critically, that none of the three
 * badges ever carry the payment-status-reserved bg-success / bg-warning /
 * bg-destructive classes (00-architecture-and-standards.md §3.1).
 */
test("occupancy badge maps each status to its own token, never success/warning/destructive", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.route(`${MOCK_API_PREFIX}/towers/*/flats*`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "flat-vacant",
            tower_id: TOWER_A.tower_id,
            flat_number: "101",
            floor: 1,
            type: "2BHK",
            carpet_area_sqft: 850,
            occupancy_status: "vacant",
            primary_owner: null,
            active_tenant: null,
            deactivated_at: null,
          },
          {
            id: "flat-owner-occupied",
            tower_id: TOWER_A.tower_id,
            flat_number: "102",
            floor: 1,
            type: "2BHK",
            carpet_area_sqft: 850,
            occupancy_status: "owner_occupied",
            primary_owner: { id: "owner-1", full_name: "Priya Owner", phone: "9876500000", email: null },
            active_tenant: null,
            deactivated_at: null,
          },
          {
            id: "flat-tenant-occupied",
            tower_id: TOWER_A.tower_id,
            flat_number: "103",
            floor: 1,
            type: "3BHK",
            carpet_area_sqft: 1100,
            occupancy_status: "tenant_occupied",
            primary_owner: { id: "owner-2", full_name: "Raj Owner", phone: "9876500001", email: null },
            active_tenant: { id: "tenant-1", full_name: "Tara Tenant", phone: "9876500002", email: null },
            deactivated_at: null,
          },
        ],
        page: 1,
        page_size: 100,
        total: 3,
      }),
    });
  });

  await page.goto(`/towers/${TOWER_A.tower_id}/flats`);

  const vacantBadge = page.getByText("Vacant", { exact: true });
  const ownerOccupiedBadge = page.getByText("Owner-occupied", { exact: true });
  const tenantOccupiedBadge = page.getByText("Tenant-occupied", { exact: true });

  await expect(vacantBadge).toBeVisible();
  await expect(ownerOccupiedBadge).toBeVisible();
  await expect(tenantOccupiedBadge).toBeVisible();

  for (const badge of [vacantBadge, ownerOccupiedBadge, tenantOccupiedBadge]) {
    const className = await badge.getAttribute("class");
    expect(className).not.toMatch(/bg-success|bg-warning|bg-destructive/);
  }

  // Tenant-occupied is the one occupancy status allowed to use the gold
  // accent token (frontend.md); the other two must not.
  await expect(tenantOccupiedBadge).toHaveClass(/bg-accent/);
  const ownerClassName = await ownerOccupiedBadge.getAttribute("class");
  expect(ownerClassName).not.toMatch(/bg-accent/);
});
