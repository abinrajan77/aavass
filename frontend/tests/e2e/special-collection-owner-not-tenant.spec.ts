import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, mockCommonListEndpoints, seedSessionCookie, TOWER_A } from "../mocks/api";

/**
 * frontend.md e2e test #2: "Special collection created while a tenant is on
 * record still assigns the owner." The actual owner-vs-tenant assignment
 * logic is a Module 2/backend concern (backend.md's due-generation query
 * always snapshots the flat's primary Owner, never a Tenant) — there is no
 * live backend in this repo yet (Module 4's backend is being built
 * concurrently, and Module 2 doesn't exist at all yet), so this asserts the
 * *frontend* contract instead: the dues table's "Responsible Party" column
 * renders the API's `owner_name` field, and never a tenant's name, given a
 * fixture due row from a tenant-occupied flat.
 */
test("collection detail dues table shows the owner as Responsible Party, never a tenant", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  const collectionId = "sc-1";

  await page.route(`${MOCK_API_PREFIX}/special-collections/*`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: collectionId,
        tower_id: TOWER_A.tower_id,
        title: "Lift Modernization Fund",
        description: null,
        total_amount: 100000,
        split_basis: "equal",
        due_date: "2026-09-01",
        dues_generated_at: new Date().toISOString(),
        skipped_flats: [],
        collected_amount: 0,
        pending_count: 1,
        paid_count: 0,
        overdue_count: 0,
        created_at: new Date().toISOString(),
      }),
    });
  });

  await page.route(`${MOCK_API_PREFIX}/special-collections/*/dues*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "due-1",
            special_collection_id: collectionId,
            flat_id: "flat-101",
            flat_number: "101",
            owner_id: "owner-1",
            owner_name: "Asha Owner",
            amount: 5000,
            due_date: "2026-09-01",
            status: "pending",
          },
        ],
        page: 1,
        page_size: 100,
        total: 1,
      }),
    });
  });

  await page.goto(`/towers/${TOWER_A.tower_id}/special-collections/${collectionId}`);

  await expect(page.getByRole("cell", { name: "Asha Owner" })).toBeVisible();
  await expect(page.getByText("Ravi Tenant")).toHaveCount(0);
});
