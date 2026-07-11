import { test, expect } from "@playwright/test";
import { MOCK_API_PREFIX, OWNER_SESSION, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";

/**
 * specs/05-reporting-owner-portal-notifications/frontend.md "Frontend Test
 * Plan": "owner with flats in 2 towers logs in, lands on `/my-flats`, opens
 * the Command palette, switches to Tower B's flat, and the dashboard
 * reloads showing only Tower B's due/payment/receipt/expenditure/tenant
 * data — no stale Tower A figures visible during or after the transition
 * (assert on a Tower-A-only sentinel value being absent post-switch)."
 */

const FLATS_SUMMARY = {
  towers: [
    {
      tower_id: "tower-a",
      tower_name: "Oakwood Tower",
      flats: [
        {
          flat_id: "flat-a1",
          tower_id: "tower-a",
          tower_name: "Oakwood Tower",
          flat_number: "A-101",
          occupancy_status: "owner_occupied",
          is_primary_owner: true,
          current_due_status: "pending",
        },
      ],
    },
    {
      tower_id: "tower-b",
      tower_name: "Sunset Tower",
      flats: [
        {
          flat_id: "flat-b1",
          tower_id: "tower-b",
          tower_name: "Sunset Tower",
          flat_number: "B-201",
          occupancy_status: "owner_occupied",
          is_primary_owner: true,
          current_due_status: "paid",
        },
      ],
    },
  ],
};

function dashboardFor(flatId: string, towerId: string, flatNumber: string, sentinelDescription: string) {
  return {
    flat_id: flatId,
    tower_id: towerId,
    flat_number: flatNumber,
    current_due: null,
    payment_history: [],
    receipts: [],
    tower_expenditures: [
      {
        date: "2026-06-01",
        category: "cleaning",
        description: sentinelDescription,
        vendor_payee: "Vendor",
        amount: 500,
        payment_mode: "cash",
        has_attachment: false,
      },
    ],
    tenant_history: [],
    ytd_totals: { total_due_ytd: 0, total_paid_ytd: 0 },
  };
}

const TOWER_A_SENTINEL = "TOWER-A-ONLY-EXPENDITURE";
const TOWER_B_SENTINEL = "TOWER-B-ONLY-EXPENDITURE";

test("owner switches flat context via the Command palette with no stale Tower A data after switching", async ({
  page,
}) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, OWNER_SESSION);

  await page.route(`${MOCK_API_PREFIX}/owners/me/flats-summary`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FLATS_SUMMARY) })
  );

  await page.route(`${MOCK_API_PREFIX}/owners/me/flats/flat-a1/dashboard`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(dashboardFor("flat-a1", "tower-a", "A-101", TOWER_A_SENTINEL)),
    })
  );
  await page.route(`${MOCK_API_PREFIX}/owners/me/flats/flat-b1/dashboard`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(dashboardFor("flat-b1", "tower-b", "B-201", TOWER_B_SENTINEL)),
    })
  );

  await page.goto("/my-flats");

  // Multiple flats -> picker, not an auto-redirect.
  await expect(page.getByText("Oakwood Tower")).toBeVisible();
  await expect(page.getByText("Sunset Tower")).toBeVisible();

  await page.getByText("Flat A-101").click();
  await expect(page).toHaveURL(/\/my-flats\/flat-a1\/dashboard$/);
  await expect(page.getByText(TOWER_A_SENTINEL)).toBeVisible();
  await expect(page.getByText(TOWER_B_SENTINEL)).toHaveCount(0);

  // Switch context via the ⌘K flat switcher's visible trigger button.
  await page.getByRole("button", { name: "Switch flat" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByText("Flat B-201").click();

  await expect(page).toHaveURL(/\/my-flats\/flat-b1\/dashboard$/);
  await expect(page.getByText(TOWER_B_SENTINEL)).toBeVisible();
  // No stale Tower A figures visible after the switch.
  await expect(page.getByText(TOWER_A_SENTINEL)).toHaveCount(0);
});
