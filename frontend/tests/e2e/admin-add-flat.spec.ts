import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, TOWER_A, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";

/**
 * specs/02-flat-owner-tenant/frontend.md E2E scenario: "Admin logs in ->
 * navigates to /towers/[towerId]/flats -> adds a new flat -> flat appears
 * in the DataTable with a Vacant badge."
 */
test("admin adds a new flat and it appears in the list with a Vacant badge", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  const flats: unknown[] = [];

  await page.route(`${MOCK_API_PREFIX}/towers/*/flats*`, async (route) => {
    const request = route.request();
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: flats, page: 1, page_size: 100, total: flats.length }),
      });
      return;
    }
    if (request.method() === "POST") {
      const body = request.postDataJSON();
      const created = {
        id: "flat-new",
        tower_id: TOWER_A.tower_id,
        flat_number: body.flat_number,
        floor: body.floor,
        type: body.type,
        carpet_area_sqft: body.carpet_area_sqft,
        occupancy_status: "vacant",
        primary_owner: null,
        active_tenant: null,
        deactivated_at: null,
      };
      flats.push(created);
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(created) });
      return;
    }
    await route.fallback();
  });

  await page.goto(`/towers/${TOWER_A.tower_id}/flats`);
  await expect(page.getByText("No flats yet.")).toBeVisible();

  await page.getByRole("button", { name: "Add Flat" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Flat number").fill("301");
  await dialog.getByLabel("Floor").fill("3");
  await dialog.getByLabel("Carpet area (sqft)").fill("600");
  await dialog.getByRole("button", { name: "Add flat" }).click();

  await expect(page.getByText("Flat created")).toBeVisible();
  await expect(page.getByRole("cell", { name: "301" })).toBeVisible();
  await expect(page.getByText("Vacant", { exact: true })).toBeVisible();
});
