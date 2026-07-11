import { test, expect } from "@playwright/test";
import { MOCK_API_PREFIX, OWNER_SESSION, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";

/**
 * specs/05-reporting-owner-portal-notifications/frontend.md "Frontend Test
 * Plan": "owner with a flat in exactly one tower is redirected straight
 * from `/my-flats` to that flat's dashboard without seeing a picker."
 */
const SINGLE_FLAT_SUMMARY = {
  towers: [
    {
      tower_id: "tower-a",
      tower_name: "Oakwood Tower",
      flats: [
        {
          flat_id: "flat-only",
          tower_id: "tower-a",
          tower_name: "Oakwood Tower",
          flat_number: "A-101",
          occupancy_status: "owner_occupied",
          is_primary_owner: true,
          current_due_status: "no_active_due",
        },
      ],
    },
  ],
};

test("an owner with a flat in exactly one tower is redirected straight to that flat's dashboard, no picker", async ({
  page,
}) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, OWNER_SESSION);

  await page.route(`${MOCK_API_PREFIX}/owners/me/flats-summary`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SINGLE_FLAT_SUMMARY) })
  );
  await page.route(`${MOCK_API_PREFIX}/owners/me/flats/flat-only/dashboard`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        flat_id: "flat-only",
        tower_id: "tower-a",
        flat_number: "A-101",
        current_due: null,
        payment_history: [],
        receipts: [],
        tower_expenditures: [],
        tenant_history: [],
        ytd_totals: { total_due_ytd: 0, total_paid_ytd: 0 },
      }),
    })
  );

  await page.goto("/my-flats");

  await expect(page).toHaveURL(/\/my-flats\/flat-only\/dashboard$/);
  await expect(page.getByText("Flat A-101")).toBeVisible();
  // No picker ever shown — no tower-grouped heading, no "Your flats" title.
  await expect(page.getByText("Your flats")).toHaveCount(0);
  // Single flat -> no switcher friction either (fewer than 2 flats total).
  await expect(page.getByRole("button", { name: "Switch flat" })).toHaveCount(0);
});
