import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, TOWER_A, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";

/**
 * specs/05-reporting-owner-portal-notifications/frontend.md "Frontend Test
 * Plan": "admin generates the Collection vs Expenditure summary for a month
 * with recorded collections but zero expenditures — page shows
 * `total_expenditure: 0` and an explicit 'No expenditures recorded for this
 * period' empty state in the expenditure breakdown area, not a spinner stuck
 * loading or an error banner."
 */
test("collection vs expenditure summary shows a zero-expenditure empty state, not a spinner or error", async ({
  page,
}) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.route(`${MOCK_API_PREFIX}/reports/collection-vs-expenditure*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tower_id: TOWER_A.tower_id,
        period_label: "July 2026",
        maintenance_collected: 150000,
        special_collection_collected: 20000,
        total_collected: 170000,
        total_expenditure: 0,
        net: 170000,
        expenditure_by_category: [],
      }),
    })
  );

  await page.goto(`/towers/${TOWER_A.tower_id}/reports?tab=collection_vs_expenditure`);

  await expect(page.getByText("Total Expenditure")).toBeVisible();
  await expect(page.getByText("₹0.00")).toBeVisible();
  await expect(page.getByText("No expenditures recorded for this period.")).toBeVisible();
  await expect(page.getByText(/something went wrong/i)).toHaveCount(0);
});
