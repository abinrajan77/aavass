import type { Page, Route } from "@playwright/test";
import { MOCK_API_PREFIX } from "./api";

/**
 * Mocked backend fixtures for Module 3's (Maintenance Billing) frontend
 * test plan (specs/03-maintenance-billing/frontend.md §4.2). Same rationale
 * as tests/mocks/api.ts: there is no live backend in this repo yet (built
 * concurrently, to specs/03-maintenance-billing/backend.md, by another
 * agent in a separate worktree) — every route here is intercepted
 * client-side via page.route() against the same
 * `NEXT_PUBLIC_API_BASE_URL=http://localhost:3100/__mock_api__` used by
 * Module 1's tests (see playwright.config.ts). Swap for a live backend once
 * it exists; the specs assert on rendered UI, not mock internals.
 */

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

export const TOWER_ID = "tower-a";

export const FORMULA_CURRENT = {
  id: "formula-1",
  tower_id: TOWER_ID,
  base_amount: 1000,
  per_sqft_rate: 2,
  effective_from: "2026-01-01",
  created_by: "member-1",
  created_by_name: "Asha Admin",
  created_at: "2026-01-01T00:00:00Z",
};

export const GRACE_PERIOD_CURRENT = {
  id: "grace-1",
  tower_id: TOWER_ID,
  grace_period_days: 5,
  effective_from: "2026-01-01",
  created_by: "member-1",
  created_by_name: "Asha Admin",
  created_at: "2026-01-01T00:00:00Z",
};

export const CYCLE_JULY_2026 = {
  id: "cycle-1",
  tower_id: TOWER_ID,
  month: 7,
  year: 2026,
  due_date: "2026-07-10",
  status: "active" as const,
  formula_id: FORMULA_CURRENT.id,
  grace_period_days_snapshot: 5,
  total_dues: 2,
  total_collected: 0,
  pending_count: 2,
  overdue_count: 0,
  formula_snapshot: {
    base_amount: FORMULA_CURRENT.base_amount,
    per_sqft_rate: FORMULA_CURRENT.per_sqft_rate,
    effective_from: FORMULA_CURRENT.effective_from,
  },
};

/** carpet_area=600 → 1000 + 600*2 = 2200.00 — matches Module 3's formula calc exactly. */
export const DUE_OWNER_PENDING = {
  id: "due-owner-1",
  flat_id: "flat-1",
  flat_number: "A-101",
  amount: 2200,
  assigned_to_type: "owner" as const,
  assigned_to_name_snapshot: "Priya Owner",
  due_date: "2026-07-10",
  status: "pending" as const,
};

/** carpet_area=900 → 1000 + 900*2 = 2800.00. Assigned to the tenant per Module 2's occupancy rule. */
export const DUE_TENANT_PENDING = {
  id: "due-tenant-1",
  flat_id: "flat-2",
  flat_number: "B-202",
  amount: 2800,
  assigned_to_type: "tenant" as const,
  assigned_to_name_snapshot: "Ravi Tenant",
  due_date: "2026-07-10",
  status: "pending" as const,
};

export const DUE_OVERDUE = {
  id: "due-overdue-1",
  flat_id: "flat-3",
  flat_number: "C-303",
  amount: 2200,
  assigned_to_type: "owner" as const,
  assigned_to_name_snapshot: "Sunita Owner",
  due_date: "2026-06-01",
  status: "overdue" as const,
};

export async function mockBillingFormulaAndGracePeriod(page: Page) {
  await page.route(`${MOCK_API_PREFIX}/maintenance-formula/current`, (route) => json(route, FORMULA_CURRENT));
  await page.route(`${MOCK_API_PREFIX}/maintenance-formula*`, async (route) => {
    if (route.request().method() === "GET") {
      return json(route, { items: [FORMULA_CURRENT], page: 1, page_size: 100, total: 1 });
    }
    return json(route, FORMULA_CURRENT, 201);
  });
  await page.route(`${MOCK_API_PREFIX}/grace-period-config/current`, (route) => json(route, GRACE_PERIOD_CURRENT));
  await page.route(`${MOCK_API_PREFIX}/grace-period-config*`, async (route) => {
    if (route.request().method() === "GET") {
      return json(route, { items: [GRACE_PERIOD_CURRENT], page: 1, page_size: 100, total: 1 });
    }
    return json(route, { ...GRACE_PERIOD_CURRENT, grace_period_days: 0 }, 201);
  });
}

export async function mockBillingCyclesList(page: Page, cycles: unknown[] = [CYCLE_JULY_2026]) {
  await page.route(`${MOCK_API_PREFIX}/billing-cycles*`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await json(route, { items: cycles, page: 1, page_size: 100, total: cycles.length });
  });
}

export async function mockCycleDetail(page: Page, cycle: unknown = CYCLE_JULY_2026) {
  await page.route(`${MOCK_API_PREFIX}/billing-cycles/${(cycle as { id: string }).id}`, (route) => json(route, cycle));
}

export async function mockCycleDues(page: Page, cycleId: string, dues: unknown[]) {
  await page.route(`${MOCK_API_PREFIX}/billing-cycles/${cycleId}/dues*`, (route) =>
    json(route, { items: dues, page: 1, page_size: 100, total: dues.length })
  );
}

export async function mockTowerDues(page: Page, dues: unknown[]) {
  await page.route(`${MOCK_API_PREFIX}/dues?*`, (route) =>
    json(route, { items: dues, page: 1, page_size: 100, total: dues.length })
  );
  await page.route(`${MOCK_API_PREFIX}/dues`, (route) =>
    json(route, { items: dues, page: 1, page_size: 100, total: dues.length })
  );
}

export async function mockBillingDashboardStats(
  page: Page,
  stats = { total_collected_this_cycle: 0, pending_count: 2, overdue_amount: 0 }
) {
  await page.route(`${MOCK_API_PREFIX}/billing-dashboard-stats*`, (route) => json(route, stats));
}

export async function mockMarkPaid(page: Page, dueId: string, paidDue: unknown, receipt: unknown) {
  await page.route(`${MOCK_API_PREFIX}/dues/${dueId}/mark-paid`, (route) =>
    json(route, { due: paidDue, receipt })
  );
}

export async function mockReceiptDownload(page: Page, dueId: string, downloadUrl: string) {
  await page.route(`${MOCK_API_PREFIX}/dues/${dueId}/receipt`, (route) =>
    json(route, { receipt_number: "OAK-2026-000001", download_url: downloadUrl })
  );
}
