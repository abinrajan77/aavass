import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, mockCommonListEndpoints, seedSessionCookie, TOWER_A } from "../mocks/api";

/**
 * frontend.md e2e test #1: "Live per-flat split preview." Creating a
 * special collection with total_amount=100000 on a tower fixture with 20
 * active flats shows "≈ ₹5,000.00 per flat across 20 flats" in the dialog
 * preview before submit, and updates reactively for a non-even split.
 *
 * mockCommonListEndpoints seeds the active-flat-count fallback endpoint
 * (`GET .../flats?status=active&count_only=true`) with `{ count: 20 }`.
 */
test("special collection create dialog shows a live, reactive per-flat split preview", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.route(`${MOCK_API_PREFIX}/towers/*`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: TOWER_A.tower_id,
        complex_id: "complex-1",
        name: "Oakwood Tower",
        code: "OAK",
        total_floors: 10,
        total_flats: 20,
        association_name: "Oakwood Owners Association",
        deactivated_at: null,
        created_at: new Date().toISOString(),
      }),
    });
  });

  await page.goto(`/towers/${TOWER_A.tower_id}/special-collections`);
  await page.getByRole("button", { name: "New special collection" }).click();

  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Total amount").fill("100000");

  await expect(dialog.getByTestId("split-preview")).toContainText("₹5,000.00 per flat across 20 flats", {
    timeout: 2000,
  });

  // A total that doesn't divide evenly across 20 flats: 10,000,001 paise / 20
  // => base 500,000 paise, remainder 1 — one flat gets an extra paisa,
  // matching the backend's remainder-distribution rule (backend.md).
  await dialog.getByLabel("Total amount").fill("100000.01");
  await expect(dialog.getByTestId("split-preview")).toContainText(
    "₹5,000.00–₹5,000.01 per flat across 20 flats",
    { timeout: 2000 }
  );
  await expect(dialog.getByTestId("split-preview")).toContainText("1 flat at ₹5,000.01, 19 at ₹5,000.00");
});
