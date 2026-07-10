import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, TOWER_A, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";

const FLAT_ID = "flat-tenant-occupied";

const FLAT = {
  id: FLAT_ID,
  tower_id: TOWER_A.tower_id,
  flat_number: "201",
  floor: 2,
  type: "3BHK",
  carpet_area_sqft: 1200,
  occupancy_status: "tenant_occupied",
  primary_owner: null,
  active_tenant: { id: "tenant-1", full_name: "Tara Tenant", phone: "9876500002", email: null },
  deactivated_at: null,
};

const TENANT = {
  id: "tenant-1",
  flat_id: FLAT_ID,
  full_name: "Tara Tenant",
  phone: "9876500002",
  email: null,
  id_number: null,
  lease_start: "2025-01-01",
  lease_end: null,
  is_active: true,
  vacated_at: null,
  created_at: new Date().toISOString(),
};

/**
 * specs/02-flat-owner-tenant/frontend.md frontend test plan: "The vacate
 * Dialog's submit button stays disabled until occupancy_status is
 * selected" — backend.md's TenantVacate.occupancy_status has no default
 * (PRD §6.2.3), so the UI must not let an admin submit without an explicit
 * choice.
 */
test("vacate dialog's submit button is disabled until occupancy_status is chosen", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.route(`${MOCK_API_PREFIX}/towers/*/flats/${FLAT_ID}`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FLAT) });
  });
  await page.route(`${MOCK_API_PREFIX}/towers/*/flats/${FLAT_ID}/owners`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route(`${MOCK_API_PREFIX}/towers/*/flats/${FLAT_ID}/tenants`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([TENANT]) });
  });

  await page.goto(`/towers/${TOWER_A.tower_id}/flats/${FLAT_ID}`);

  await page.getByRole("tab", { name: "Tenants" }).click();
  await page.getByRole("button", { name: "Vacate" }).click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();

  const submitButton = dialog.getByRole("button", { name: "Vacate tenant" });
  await expect(submitButton).toBeDisabled();

  // Filling only the date should still leave it disabled — occupancy_status
  // is the field with no default.
  await dialog.getByRole("button", { name: "Pick a date" }).click();
  await page.locator("button[data-day]").first().click();
  await page.keyboard.press("Escape"); // close the Calendar popover before it can intercept the next click
  await expect(submitButton).toBeDisabled();

  await dialog.getByRole("combobox").click();
  await page.getByRole("option", { name: "Owner-occupied" }).click();

  await expect(submitButton).toBeEnabled();
});
