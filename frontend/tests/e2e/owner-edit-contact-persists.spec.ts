import { test, expect } from "@playwright/test";
import {
  ADMIN_SESSION,
  MOCK_API_PREFIX,
  OWNER_SESSION,
  OWNER_USER_ID,
  TOWER_A,
  mockCommonListEndpoints,
  seedSessionCookie,
} from "../mocks/api";

const FLAT_ID = "flat-contact-test";

/**
 * specs/02-flat-owner-tenant/frontend.md E2E scenario: "Flat owner logs in
 * -> /my-flats/[flatId] -> Details tab shows flat fields as read-only text
 * ... -> owner edits their phone number and saves -> change persists and is
 * reflected on the admin's view of the same owner."
 *
 * Simulates the "same underlying data, both surfaces read the same API"
 * guarantee by mutating one shared, stateful `owner` fixture object from
 * the owner-surface PATCH and reading it back from the admin surface's
 * GET .../owners — no live backend needed to prove the frontend wiring is
 * correct end to end.
 */
test("owner's phone edit on /my-flats persists and is visible on the admin's Owners tab", async ({ page }) => {
  await mockCommonListEndpoints(page);

  const flat = {
    id: FLAT_ID,
    tower_id: TOWER_A.tower_id,
    flat_number: "701",
    floor: 7,
    type: "2BHK",
    carpet_area_sqft: 800,
    occupancy_status: "owner_occupied",
    primary_owner: { id: "owner-1", full_name: "Priya Owner", phone: "9876500000", email: "priya@owner.test" },
    active_tenant: null,
    deactivated_at: null,
  };
  const owner = {
    id: "owner-1",
    user_id: OWNER_USER_ID,
    full_name: "Priya Owner",
    phone: "9876500000",
    email: "priya@owner.test",
    id_number: null as string | null,
    created_at: new Date().toISOString(),
    deactivated_at: null,
  };
  const ownership = {
    id: "ownership-1",
    flat_id: FLAT_ID,
    owner_id: "owner-1",
    owner,
    is_primary_contact: true,
    date_from: "2024-01-01",
    date_to: null,
    created_at: new Date().toISOString(),
  };

  await page.route(`${MOCK_API_PREFIX}/me/flats`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([flat]) });
  });
  await page.route(`${MOCK_API_PREFIX}/towers/*/flats/${FLAT_ID}`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(flat) });
  });
  await page.route(`${MOCK_API_PREFIX}/towers/*/flats/${FLAT_ID}/owners`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([ownership]) });
  });
  await page.route(`${MOCK_API_PREFIX}/owners/owner-1`, async (route) => {
    if (route.request().method() !== "PATCH") return route.fallback();
    const body = route.request().postDataJSON();
    if (body.phone) owner.phone = body.phone;
    if (body.email) owner.email = body.email;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(owner) });
  });

  await seedSessionCookie(page, OWNER_SESSION);
  await page.goto(`/my-flats/${FLAT_ID}`);

  const phoneInput = page.getByLabel("Phone");
  await expect(phoneInput).toHaveValue("9876500000");
  await phoneInput.fill("9998887777");
  await page.getByRole("button", { name: "Save contact details" }).click();
  await expect(page.getByText("Contact details updated")).toBeVisible();

  // Switch to the admin session and view the same owner via the tower-scoped route.
  await seedSessionCookie(page, ADMIN_SESSION);
  await page.goto(`/towers/${TOWER_A.tower_id}/flats/${FLAT_ID}`);
  await page.getByRole("tab", { name: "Owners" }).click();

  await expect(page.getByText("9998887777")).toBeVisible();
});
