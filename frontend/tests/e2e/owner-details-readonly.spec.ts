import { test, expect } from "@playwright/test";
import { MOCK_API_PREFIX, OWNER_SESSION, OWNER_USER_ID, seedSessionCookie } from "../mocks/api";

const TOWER_ID = "tower-a";
const FLAT_ID = "flat-owned-1";

const FLAT = {
  id: FLAT_ID,
  tower_id: TOWER_ID,
  flat_number: "404",
  floor: 4,
  type: "3BHK",
  carpet_area_sqft: 1350,
  occupancy_status: "owner_occupied",
  primary_owner: { id: "owner-1", full_name: "Priya Owner", phone: "9876500000", email: "priya@owner.test" },
  active_tenant: null,
  deactivated_at: null,
};

const OWNERSHIP = {
  id: "ownership-1",
  flat_id: FLAT_ID,
  owner_id: "owner-1",
  owner: {
    id: "owner-1",
    user_id: OWNER_USER_ID,
    full_name: "Priya Owner",
    phone: "9876500000",
    email: "priya@owner.test",
    id_number: "ID-123",
    created_at: new Date().toISOString(),
    deactivated_at: null,
  },
  is_primary_contact: true,
  date_from: "2024-01-01",
  date_to: null,
  created_at: new Date().toISOString(),
};

/**
 * specs/02-flat-owner-tenant/frontend.md frontend test plan: "/my-flats/
 * [flatId] Details tab renders carpet_area/floor/type/flat_number as plain
 * text (no <input> present in the DOM) for a session with only
 * MANAGE_OWN_FLAT." Also covers the "must NOT break" rule: identity fields
 * (full_name, id_number) must never render as editable inputs here even
 * though this fixture's Owner *has* an id_number value — it must not
 * surface as an <input>.
 */
test("/my-flats/[flatId] Details tab renders flat fields as read-only text, never inputs", async ({ page }) => {
  await seedSessionCookie(page, OWNER_SESSION);

  await page.route(`${MOCK_API_PREFIX}/me/flats`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([FLAT]) });
  });
  await page.route(`${MOCK_API_PREFIX}/towers/*/flats/${FLAT_ID}/owners`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([OWNERSHIP]) });
  });

  await page.goto(`/my-flats/${FLAT_ID}`);

  // Flat fields visible as plain text...
  await expect(page.getByText("404", { exact: true })).toBeVisible();
  await expect(page.getByText("4", { exact: true })).toBeVisible();
  await expect(page.getByText("3BHK", { exact: true })).toBeVisible();
  await expect(page.getByText("1350 sqft")).toBeVisible();

  // ...and never as <input> elements. Only the contact form's phone/email
  // fields may render as inputs on this tab.
  await expect(page.locator("input")).toHaveCount(2);
  await expect(page.getByLabel("Phone")).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();

  // Identity fields must never appear as an editable input, even though
  // this Owner fixture has an id_number.
  await expect(page.getByLabel("Full name")).toHaveCount(0);
  await expect(page.getByLabel("ID number")).toHaveCount(0);
  await expect(page.locator("input[name='full_name']")).toHaveCount(0);
  await expect(page.locator("input[name='id_number']")).toHaveCount(0);
});
