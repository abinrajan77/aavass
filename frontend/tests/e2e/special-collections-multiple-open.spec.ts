import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, mockCommonListEndpoints, seedSessionCookie, TOWER_A } from "../mocks/api";

/**
 * frontend.md e2e test #7: "Multiple open collections render independently."
 * Two open special collections seeded on the same tower: the list shows
 * both with independent progress/collected-amount figures, and navigating
 * into each shows only its own dues.
 */
test("two open special collections render independently in the list and in detail", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.route(`${MOCK_API_PREFIX}/special-collections*`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "sc-a",
            tower_id: TOWER_A.tower_id,
            title: "Lift Modernization Fund",
            description: null,
            total_amount: 100000,
            split_basis: "equal",
            due_date: "2026-09-01",
            dues_generated_at: new Date().toISOString(),
            skipped_flats: [],
            collected_amount: 40000,
            pending_count: 12,
            paid_count: 4,
            overdue_count: 0,
            created_at: new Date().toISOString(),
          },
          {
            id: "sc-b",
            tower_id: TOWER_A.tower_id,
            title: "Facade Painting",
            description: null,
            total_amount: 60000,
            split_basis: "equal",
            due_date: "2026-10-01",
            dues_generated_at: new Date().toISOString(),
            skipped_flats: [],
            collected_amount: 0,
            pending_count: 20,
            paid_count: 0,
            overdue_count: 0,
            created_at: new Date().toISOString(),
          },
        ],
        page: 1,
        page_size: 100,
        total: 2,
      }),
    });
  });

  await page.route(`${MOCK_API_PREFIX}/special-collections/sc-a`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "sc-a",
        tower_id: TOWER_A.tower_id,
        title: "Lift Modernization Fund",
        description: null,
        total_amount: 100000,
        split_basis: "equal",
        due_date: "2026-09-01",
        dues_generated_at: new Date().toISOString(),
        skipped_flats: [],
        collected_amount: 40000,
        pending_count: 12,
        paid_count: 4,
        overdue_count: 0,
        created_at: new Date().toISOString(),
      }),
    });
  });
  await page.route(`${MOCK_API_PREFIX}/special-collections/sc-a/dues*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "due-a-1",
            special_collection_id: "sc-a",
            flat_id: "flat-101",
            flat_number: "101",
            owner_id: "owner-1",
            owner_name: "Owner A1",
            amount: 5000,
            due_date: "2026-09-01",
            status: "paid",
          },
        ],
        page: 1,
        page_size: 100,
        total: 1,
      }),
    });
  });

  await page.route(`${MOCK_API_PREFIX}/special-collections/sc-b`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "sc-b",
        tower_id: TOWER_A.tower_id,
        title: "Facade Painting",
        description: null,
        total_amount: 60000,
        split_basis: "equal",
        due_date: "2026-10-01",
        dues_generated_at: new Date().toISOString(),
        skipped_flats: [],
        collected_amount: 0,
        pending_count: 20,
        paid_count: 0,
        overdue_count: 0,
        created_at: new Date().toISOString(),
      }),
    });
  });
  await page.route(`${MOCK_API_PREFIX}/special-collections/sc-b/dues*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "due-b-1",
            special_collection_id: "sc-b",
            flat_id: "flat-201",
            flat_number: "201",
            owner_id: "owner-2",
            owner_name: "Owner B1",
            amount: 3000,
            due_date: "2026-10-01",
            status: "pending",
          },
        ],
        page: 1,
        page_size: 100,
        total: 1,
      }),
    });
  });

  await page.goto(`/towers/${TOWER_A.tower_id}/special-collections`);

  await expect(page.getByRole("link", { name: "Lift Modernization Fund" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Facade Painting" })).toBeVisible();
  // Independent progress: sc-a is 40% collected (40,000 / 100,000), sc-b is
  // 0% (0 / 60,000) — asserted via each row's own progress percentage and
  // Total Amount figure, since the list table shows a progress bar (not a
  // raw collected-amount figure) per row.
  const rows = page.locator("table tbody tr");
  // en-IN `Intl.NumberFormat` groups by the Indian numbering system (lakhs),
  // so ₹100,000 renders as "₹1,00,000.00", not "₹100,000.00".
  await expect(rows.filter({ hasText: "Lift Modernization Fund" })).toContainText("₹1,00,000.00");
  await expect(rows.filter({ hasText: "Lift Modernization Fund" })).toContainText("40%");
  await expect(rows.filter({ hasText: "Facade Painting" })).toContainText("₹60,000.00");
  await expect(rows.filter({ hasText: "Facade Painting" })).toContainText("0%");

  await page.getByRole("link", { name: "Lift Modernization Fund" }).click();
  await expect(page).toHaveURL(new RegExp("/special-collections/sc-a$"));
  await expect(page.getByRole("cell", { name: "Owner A1" })).toBeVisible();
  await expect(page.getByText("Owner B1")).toHaveCount(0);

  await page.goto(`/towers/${TOWER_A.tower_id}/special-collections/sc-b`);
  await expect(page.getByRole("cell", { name: "Owner B1" })).toBeVisible();
  await expect(page.getByText("Owner A1")).toHaveCount(0);
});
