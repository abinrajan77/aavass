import { test, expect } from "@playwright/test";
import {
  ADMIN_SESSION,
  MOCK_API_PREFIX,
  OWNER_SESSION,
  TOWER_A,
  mockCommonListEndpoints,
  seedSessionCookie,
} from "../mocks/api";

const FLAT_ID = "flat-owner-adds-tenant";

/**
 * specs/02-flat-owner-tenant/frontend.md E2E scenario: "Flat owner adds a
 * tenant for their own flat from /my-flats/[flatId] -> tenant appears
 * immediately in the admin's /towers/[towerId]/flats/[flatId] Tenants tab
 * (same underlying data, both surfaces read the same API)."
 */
test("tenant added by the owner on /my-flats is visible on the admin's Tenants tab", async ({ page }) => {
  await mockCommonListEndpoints(page);

  const flat = {
    id: FLAT_ID,
    tower_id: TOWER_A.tower_id,
    flat_number: "801",
    floor: 8,
    type: "1BHK",
    carpet_area_sqft: 550,
    occupancy_status: "vacant" as string,
    primary_owner: null,
    active_tenant: null as unknown,
    deactivated_at: null,
  };
  let tenants: Array<Record<string, unknown>> = [];

  await page.route(`${MOCK_API_PREFIX}/me/flats`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([flat]) });
  });
  await page.route(`${MOCK_API_PREFIX}/towers/*/flats/${FLAT_ID}`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(flat) });
  });
  await page.route(`${MOCK_API_PREFIX}/towers/*/flats/${FLAT_ID}/owners`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route(`${MOCK_API_PREFIX}/towers/*/flats/${FLAT_ID}/tenants**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    if (url.pathname.endsWith("/tenants") && req.method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(tenants) });
      return;
    }
    if (url.pathname.endsWith("/tenants") && req.method() === "POST") {
      const body = req.postDataJSON();
      const created = {
        id: "tenant-owner-added",
        flat_id: FLAT_ID,
        full_name: body.full_name,
        phone: body.phone,
        email: body.email ?? null,
        id_number: body.id_number ?? null,
        lease_start: body.lease_start,
        lease_end: body.lease_end ?? null,
        is_active: true,
        vacated_at: null,
        created_at: new Date().toISOString(),
      };
      tenants = [created];
      flat.occupancy_status = "tenant_occupied";
      flat.active_tenant = { id: created.id, full_name: created.full_name, phone: created.phone, email: created.email };
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(created) });
      return;
    }
    await route.fallback();
  });

  await seedSessionCookie(page, OWNER_SESSION);
  await page.goto(`/my-flats/${FLAT_ID}`);
  await page.getByRole("tab", { name: "Tenants" }).click();
  await page.getByRole("button", { name: "Add tenant" }).click();

  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Full name").fill("Owner-Added Tenant");
  await dialog.getByLabel("Phone").fill("9876511111");
  // Two DateFields render in this form (lease_start, lease_end); lease_start is first.
  await dialog.getByRole("button", { name: "Pick a date" }).first().click();
  await page.locator("button[data-day]").first().click();
  await page.keyboard.press("Escape"); // close the Calendar popover before it can intercept the next click
  await dialog.getByRole("button", { name: "Add tenant" }).click();

  await expect(page.getByText("Tenant added")).toBeVisible();

  await seedSessionCookie(page, ADMIN_SESSION);
  await page.goto(`/towers/${TOWER_A.tower_id}/flats/${FLAT_ID}`);
  await page.getByRole("tab", { name: "Tenants" }).click();

  await expect(page.getByText("Owner-Added Tenant")).toBeVisible();
});
