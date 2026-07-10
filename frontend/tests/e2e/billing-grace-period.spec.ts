import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";
import { MOCK_API_PREFIX } from "../mocks/api";
import {
  CYCLE_JULY_2026,
  DUE_OVERDUE,
  GRACE_PERIOD_CURRENT,
  TOWER_ID,
  mockBillingDashboardStats,
  mockBillingFormulaAndGracePeriod,
  mockCycleDetail,
} from "../mocks/billing";

/**
 * specs/03-maintenance-billing/frontend.md §4.2: "Grace period page: setting
 * the value to 0 and saving, then navigating to a cycle with a due exactly
 * one day past its due date, shows that due as 'Overdue'."
 *
 * Per backend.md §3 (design decision), the Pending→Overdue transition is
 * computed by a nightly backend job, not on-read — the frontend never
 * derives "Overdue" itself. This test therefore covers the two
 * frontend-owned halves of that scenario: (1) saving grace_period_days=0
 * succeeds through the form, and (2) whatever status the API returns for a
 * due (here, the backend having already flipped it to overdue) renders with
 * the destructive-token Badge, never a locally-recomputed status.
 */
test("saving grace period = 0, then viewing a cycle, renders an already-overdue due with the Overdue badge", async ({
  page,
}) => {
  await mockCommonListEndpoints(page);
  await mockBillingFormulaAndGracePeriod(page);
  await mockCycleDetail(page);
  await mockBillingDashboardStats(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  let savedGracePeriodDays: number | null = null;
  await page.route(`${MOCK_API_PREFIX}/grace-period-config`, async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    const body = route.request().postDataJSON();
    savedGracePeriodDays = body.grace_period_days;
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ ...GRACE_PERIOD_CURRENT, grace_period_days: body.grace_period_days }),
    });
  });
  await page.route(`${MOCK_API_PREFIX}/billing-cycles/${CYCLE_JULY_2026.id}/dues*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [DUE_OVERDUE], page: 1, page_size: 100, total: 1 }),
    })
  );

  await page.goto(`/towers/${TOWER_ID}/billing/grace-period`);
  await expect(page.getByText(/0 days means a due becomes overdue/i)).toBeVisible();

  const input = page.getByLabel(/grace period \(days\)/i);
  await input.fill("0");
  await page.getByRole("button", { name: "Save grace period" }).click();
  await expect(page.getByText(/grace period saved/i)).toBeVisible();
  expect(savedGracePeriodDays).toBe(0);

  await page.goto(`/towers/${TOWER_ID}/billing/cycles/${CYCLE_JULY_2026.id}`);
  const table = page.getByRole("table");
  await expect(table.getByText(DUE_OVERDUE.flat_number)).toBeVisible();
  await expect(table.getByText("Overdue")).toBeVisible();
});
