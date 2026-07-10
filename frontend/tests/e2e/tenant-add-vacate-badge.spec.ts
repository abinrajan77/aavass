import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, TOWER_A, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";

const FLAT_ID = "flat-badge-test";

/**
 * specs/02-flat-owner-tenant/frontend.md E2E scenario: "Admin adds a tenant
 * on the Tenants tab -> flat detail badge updates to Tenant-occupied
 * without a page reload (optimistic update / refetch) -> admin marks the
 * tenant vacated, selecting Owner-occupied in the dialog -> badge reverts
 * to Owner-occupied and the tenant now appears under Tenant History."
 *
 * This is the module's core cross-query-invalidation guarantee
 * (lib/hooks/use-flats.ts): adding/vacating a tenant must refresh the flat
 * detail query too, since occupancy_status is a side effect of the tenant
 * mutation, not just of the tenant list.
 */
test("adding then vacating a tenant flips the occupancy badge without a reload", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  const flat = {
    id: FLAT_ID,
    tower_id: TOWER_A.tower_id,
    flat_number: "601",
    floor: 6,
    type: "2BHK",
    carpet_area_sqft: 950,
    occupancy_status: "owner_occupied" as string,
    primary_owner: null as unknown,
    active_tenant: null as unknown,
    deactivated_at: null,
  };
  let tenants: Array<Record<string, unknown>> = [];

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
    const method = req.method();

    if (url.pathname.endsWith("/tenants") && method === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(tenants) });
      return;
    }
    if (url.pathname.endsWith("/tenants") && method === "POST") {
      const body = req.postDataJSON();
      const created = {
        id: "tenant-1",
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
    if (url.pathname.endsWith("/vacate") && method === "POST") {
      const body = req.postDataJSON();
      tenants = tenants.map((t) =>
        t.id === "tenant-1"
          ? { ...t, is_active: false, vacated_at: new Date().toISOString(), lease_end: t.lease_end ?? body.vacated_date }
          : t
      );
      flat.occupancy_status = body.occupancy_status;
      flat.active_tenant = null;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(tenants[0]) });
      return;
    }
    await route.fallback();
  });

  await page.goto(`/towers/${TOWER_A.tower_id}/flats/${FLAT_ID}`);
  await expect(page.getByText("Owner-occupied", { exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Tenants" }).click();
  await page.getByRole("button", { name: "Add tenant" }).click();

  const addDialog = page.getByRole("dialog");
  await addDialog.getByLabel("Full name").fill("Tara Tenant");
  await addDialog.getByLabel("Phone").fill("9876512399");
  // Two DateFields render in this form (lease_start, lease_end); lease_start is first.
  await addDialog.getByRole("button", { name: "Pick a date" }).first().click();
  await page.locator("button[data-day]").first().click();
  await page.keyboard.press("Escape"); // close the Calendar popover before it can intercept the next click
  await addDialog.getByRole("button", { name: "Add tenant" }).click();

  await expect(page.getByText("Tenant added")).toBeVisible();
  // Badge in the page header updates without a reload — same query
  // invalidation this test is actually verifying.
  await expect(page.getByText("Tenant-occupied", { exact: true })).toBeVisible();
  await expect(page.getByText("Owner-occupied", { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "Vacate" }).click();
  const vacateDialog = page.getByRole("dialog");
  await vacateDialog.getByRole("button", { name: "Pick a date" }).click();
  await page.locator("button[data-day]").first().click();
  await page.keyboard.press("Escape"); // close the Calendar popover before it can intercept the next click
  await vacateDialog.getByRole("combobox").click();
  await page.getByRole("option", { name: "Owner-occupied" }).click();
  await vacateDialog.getByRole("button", { name: "Vacate tenant" }).click();

  await expect(page.getByText(/Tenant vacated/)).toBeVisible();
  await expect(page.getByText("Owner-occupied", { exact: true })).toBeVisible();
  await expect(page.getByText("Tenant-occupied", { exact: true })).toHaveCount(0);
  // Vacated tenant now shows up under Tenant History.
  await expect(page.getByRole("cell", { name: "Tara Tenant" })).toBeVisible();
});
