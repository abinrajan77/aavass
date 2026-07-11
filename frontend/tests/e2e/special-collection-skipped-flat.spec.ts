import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, mockCommonListEndpoints, seedSessionCookie, TOWER_A } from "../mocks/api";

/**
 * frontend.md e2e test #3: "Skipped-flat warning surfaces in the UI." Fixture:
 * 10 active flats, one has no active owner. Creating a special collection
 * assert a post-creation toast lists the skipped flat + reason, and the
 * dues table shows one fewer row than total active flats (9, not 10).
 *
 * The backend's actual skip logic isn't exercised (no live backend) — the
 * `POST .../special-collections` response is mocked to return exactly the
 * `skipped_flats` shape backend.md specifies, and this test asserts the
 * frontend surfaces it correctly.
 */
test("skipped-flat toast appears after creation and the dues table has one fewer row", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  const collectionId = "sc-skip-1";

  await page.route(`${MOCK_API_PREFIX}/special-collections*`, async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        id: collectionId,
        tower_id: TOWER_A.tower_id,
        title: "Corpus Fund",
        description: null,
        total_amount: 90000,
        split_basis: "equal",
        due_date: "2026-09-01",
        dues_generated_at: new Date().toISOString(),
        skipped_flats: [{ flat_id: "flat-110", flat_number: "110", reason: "NO_ACTIVE_OWNER" }],
        collected_amount: 0,
        pending_count: 9,
        paid_count: 0,
        overdue_count: 0,
        created_at: new Date().toISOString(),
        dues_generated: true,
      }),
    });
  });

  await page.goto(`/towers/${TOWER_A.tower_id}/special-collections`);
  await page.getByRole("button", { name: "New special collection" }).click();

  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Title").fill("Corpus Fund");
  await dialog.getByLabel("Total amount").fill("90000");

  // The trigger button's accessible name comes from its associated
  // <FormLabel> ("Due date"), not its own "Pick a date" text content.
  await dialog.getByRole("button", { name: "Due date" }).click();
  await page.getByRole("button", { name: /next month/i }).click();
  await page.locator("[data-day]:not([disabled])").first().click();

  await dialog.getByRole("button", { name: "Create special collection" }).click();

  await expect(page.getByText(/skipped 1 flat.*110/i)).toBeVisible();

  // Navigate into the created collection's detail page (mocked) and assert
  // 9 due rows (10 active flats - 1 skipped).
  await page.route(`${MOCK_API_PREFIX}/special-collections/*`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: collectionId,
        tower_id: TOWER_A.tower_id,
        title: "Corpus Fund",
        description: null,
        total_amount: 90000,
        split_basis: "equal",
        due_date: "2026-09-01",
        dues_generated_at: new Date().toISOString(),
        skipped_flats: [{ flat_id: "flat-110", flat_number: "110", reason: "NO_ACTIVE_OWNER" }],
        collected_amount: 0,
        pending_count: 9,
        paid_count: 0,
        overdue_count: 0,
        created_at: new Date().toISOString(),
      }),
    });
  });
  await page.route(`${MOCK_API_PREFIX}/special-collections/*/dues*`, async (route) => {
    const items = Array.from({ length: 9 }, (_, i) => ({
      id: `due-${i + 1}`,
      special_collection_id: collectionId,
      flat_id: `flat-${101 + i}`,
      flat_number: `${101 + i}`,
      owner_id: `owner-${i + 1}`,
      owner_name: `Owner ${i + 1}`,
      amount: 10000,
      due_date: "2026-09-01",
      status: "pending",
    }));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items, page: 1, page_size: 100, total: 9 }),
    });
  });

  await page.goto(`/towers/${TOWER_A.tower_id}/special-collections/${collectionId}`);
  await expect(page.getByText("1 flat(s) skipped")).toBeVisible();
  await expect(page.locator("table tbody tr")).toHaveCount(9);
});
