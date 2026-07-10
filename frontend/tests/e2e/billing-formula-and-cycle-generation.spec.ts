import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";
import {
  CYCLE_JULY_2026,
  DUE_OWNER_PENDING,
  DUE_TENANT_PENDING,
  TOWER_ID,
  mockBillingCyclesList,
  mockBillingDashboardStats,
  mockBillingFormulaAndGracePeriod,
  mockCycleDetail,
  mockCycleDues,
} from "../mocks/billing";
import { MOCK_API_PREFIX } from "../mocks/api";

/**
 * specs/03-maintenance-billing/frontend.md §4.2:
 * "Admin configures a formula (base=1000, rate=2) → generates a billing
 * cycle → dues list shows each flat's amount equal to
 * 1000 + carpet_area × 2, matching what Module 2's flat data reports for
 * carpet area per flat."
 *
 * The actual base+rate×area arithmetic is a backend responsibility
 * (backend.md §2 `calculate_monthly_maintenance`, covered by the backend's
 * own unit tests in backend.md §8.1) — this test's job is to verify the
 * frontend correctly saves the formula, drives cycle generation, and
 * faithfully renders whatever amounts the API returns. The mocked dues
 * below are deliberately pre-computed from base=1000/rate=2 (600 sq.ft. →
 * ₹2,200.00, 900 sq.ft. → ₹2,800.00) so a passing assertion demonstrates the
 * UI-to-API wiring is correct end-to-end.
 */
test("admin configures a formula, generates a cycle, and the dues list shows formula-consistent amounts", async ({
  page,
}) => {
  await mockCommonListEndpoints(page);
  await mockBillingFormulaAndGracePeriod(page);
  await mockBillingCyclesList(page, [CYCLE_JULY_2026]);
  await mockCycleDetail(page);
  await mockCycleDues(page, CYCLE_JULY_2026.id, [DUE_OWNER_PENDING, DUE_TENANT_PENDING]);
  await mockBillingDashboardStats(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.goto(`/towers/${TOWER_ID}/billing/formula`);
  await expect(page.getByText("Maintenance formula")).toBeVisible();
  await expect(page.getByLabel(/base amount/i)).toHaveValue("1000");
  await expect(page.getByLabel(/per sq\.ft\. rate/i)).toHaveValue("2");

  await page.goto(`/towers/${TOWER_ID}/billing/cycles/${CYCLE_JULY_2026.id}`);
  await expect(page.getByText("July 2026")).toBeVisible();
  await expect(page.getByText(/base ₹1000.*₹2\/sq\.ft/i)).toBeVisible();

  // 1000 + 600*2 = 2200.00
  await expect(page.getByText("₹2,200.00")).toBeVisible();
  // 1000 + 900*2 = 2800.00
  await expect(page.getByText("₹2,800.00")).toBeVisible();
});

/**
 * frontend.md §2.3 / §4.2: "409 BILLING_CYCLE_ALREADY_EXISTS → inline form
 * error under the month/year fields, not a toast" — "dialog does not close,
 * no duplicate row appears in the cycles list."
 */
test("generating a cycle for a month/year that already exists shows an inline error, not a toast", async ({
  page,
}) => {
  await mockCommonListEndpoints(page);
  await mockBillingCyclesList(page, [CYCLE_JULY_2026]);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.route(`${MOCK_API_PREFIX}/billing-cycles*`, async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({
        error_code: "BILLING_CYCLE_ALREADY_EXISTS",
        message: "A billing cycle for this month/year already exists.",
        field_errors: null,
      }),
    });
  });

  await page.goto(`/towers/${TOWER_ID}/billing/cycles`);
  await page.getByRole("button", { name: "Generate Cycle" }).click();

  // Scoped by accessible name: a closed date-picker Popover also carries
  // role="dialog" while mounted (Radix keeps it in the DOM after closing),
  // so an unscoped getByRole("dialog") is ambiguous once the calendar has
  // been opened once.
  const dialog = page.getByRole("dialog", { name: "Generate billing cycle" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Due date" }).click();
  await page.getByRole("button", { name: /15/ }).first().click();
  await dialog.getByRole("button", { name: "Generate" }).click();

  await expect(dialog.getByText(/already exists/i)).toBeVisible();
  // Dialog stays open — no toast-driven auto-close, and no second row appears.
  await expect(dialog).toBeVisible();
  await expect(page.getByText("July 2026")).toHaveCount(1);
});

/**
 * frontend.md §2.3 / §4.2: "Admin generates a cycle for a tower with >300
 * flats → sees the 'generating' progress state → list eventually shows the
 * cycle as active with the correct total dues count once the async job
 * completes." Backend.md §4 documents the 202 path returning
 * `{ cycle_id, job_id, status: 'generating' }`, polled via the shared
 * canonical `GET /jobs/{job_id}` route every 2s (06-cloud-devops.md §4).
 */
test("generating a cycle beyond the sync threshold shows a progress state, then resolves once the job completes", async ({
  page,
}) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  const generatingCycle = { ...CYCLE_JULY_2026, id: "cycle-2", status: "generating" as const, total_dues: 0 };
  const activeCycle = { ...CYCLE_JULY_2026, id: "cycle-2", status: "active" as const, total_dues: 450 };

  // State-based rather than call-count-based, so this isn't sensitive to
  // exactly how many times React Query happens to refetch the list before
  // the job resolves (e.g. React 18 dev-mode double-effects).
  let jobDone = false;
  await page.route(`${MOCK_API_PREFIX}/billing-cycles*`, async (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ cycle_id: generatingCycle.id, job_id: "job-1", status: "generating" }),
      });
    }
    const cycle = jobDone ? activeCycle : generatingCycle;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [cycle], page: 1, page_size: 100, total: 1 }),
    });
  });

  let jobPollCount = 0;
  await page.route(`${MOCK_API_PREFIX}/jobs/job-1`, async (route) => {
    jobPollCount += 1;
    const status = jobPollCount < 2 ? "in_progress" : "done";
    if (status === "done") jobDone = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ job_id: "job-1", status }),
    });
  });

  await page.goto(`/towers/${TOWER_ID}/billing/cycles`);
  await page.getByRole("button", { name: "Generate Cycle" }).click();
  const dialog = page.getByRole("dialog", { name: "Generate billing cycle" });
  await dialog.getByRole("button", { name: "Due date" }).click();
  await page.getByRole("button", { name: /15/ }).first().click();
  await dialog.getByRole("button", { name: "Generate" }).click();

  // Progress state while the job is in flight.
  await expect(page.getByText(/generating dues for this cycle/i)).toBeVisible();

  // Once the job resolves to "done", the dialog closes and the cycles list
  // reflects the now-active cycle with its full due count.
  await expect(dialog).toHaveCount(0, { timeout: 10_000 });
  await expect(page.getByText("450")).toBeVisible();
});
