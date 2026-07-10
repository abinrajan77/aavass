import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, TOWER_A, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";

const FLAT_ID = "flat-no-owners";

const FLAT = {
  id: FLAT_ID,
  tower_id: TOWER_A.tower_id,
  flat_number: "501",
  floor: 5,
  type: "2BHK",
  carpet_area_sqft: 900,
  occupancy_status: "vacant",
  primary_owner: null,
  active_tenant: null,
  deactivated_at: null,
};

/**
 * specs/02-flat-owner-tenant/frontend.md E2E scenario: "Admin opens the flat
 * -> Owners tab -> adds an owner as primary contact -> Owners tab shows the
 * owner with a 'Primary' badge."
 */
test("admin adds a co-owner as primary contact and the Owners tab shows the Primary badge", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  let ownerships: unknown[] = [];

  await page.route(`${MOCK_API_PREFIX}/towers/*/flats/${FLAT_ID}`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FLAT) });
  });

  await page.route(`${MOCK_API_PREFIX}/towers/*/flats/${FLAT_ID}/tenants`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });

  await page.route(`${MOCK_API_PREFIX}/towers/*/flats/${FLAT_ID}/owners`, async (route) => {
    const request = route.request();
    if (request.method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ownerships) });
      return;
    }
    if (request.method() === "POST") {
      const body = request.postDataJSON();
      const created = {
        id: "ownership-new",
        flat_id: FLAT_ID,
        owner_id: "owner-new",
        owner: {
          id: "owner-new",
          user_id: null,
          full_name: body.full_name,
          phone: body.phone,
          email: body.email ?? null,
          id_number: body.id_number ?? null,
          created_at: new Date().toISOString(),
          deactivated_at: null,
        },
        is_primary_contact: body.is_primary_contact,
        date_from: body.date_from,
        date_to: null,
        created_at: new Date().toISOString(),
      };
      ownerships = [created];
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(created) });
      return;
    }
    await route.fallback();
  });

  await page.goto(`/towers/${TOWER_A.tower_id}/flats/${FLAT_ID}`);
  await page.getByRole("tab", { name: "Owners" }).click();

  await page.getByRole("button", { name: "Add co-owner" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Full name").fill("Nita Nair");
  await dialog.getByLabel("Phone").fill("9876512345");
  await dialog.getByRole("button", { name: "Pick a date" }).click();
  await page.locator("button[data-day]").first().click();
  await page.keyboard.press("Escape"); // close the Calendar popover before it can intercept the next click
  await dialog.getByLabel("Make primary contact").check();
  await dialog.getByRole("button", { name: "Add owner" }).click();

  await expect(page.getByText("Owner added")).toBeVisible();
  await expect(page.getByText("Nita Nair")).toBeVisible();
  await expect(page.getByText("Primary", { exact: true })).toBeVisible();
});
