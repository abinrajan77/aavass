import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, mockCommonListEndpoints, seedSessionCookie, TOWER_A } from "../mocks/api";

/**
 * frontend.md e2e test #6: "Complex-contribution form only posts the
 * tower's share to the ledger." Submitting
 * `/expenditures/new?type=complex-contribution` with
 * complex_total_amount=500000 and tower's share 80000 — on the resulting
 * `/expenditures` list, the row's displayed Amount is 80000.00 and the
 * category-totals summary reflects only that figure.
 */
test("complex-contribution form posts only the tower's share, never the complex total", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  let capturedBody: Record<string, unknown> | null = null;
  await page.route(`${MOCK_API_PREFIX}/expenditures/complex-contribution`, async (route) => {
    capturedBody = route.request().postDataJSON();
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        id: "exp-1",
        tower_id: TOWER_A.tower_id,
        expenditure_date: "2026-07-05",
        category: "other",
        description: "Complex-wide painting",
        vendor_payee_name: "XYZ Painters",
        amount: 80000,
        payment_mode: "cheque",
        attachment_s3_key: null,
        is_complex_contribution: true,
        complex_total_amount: 500000,
        recorded_by: "user-1",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        deactivated_at: null,
      }),
    });
  });

  await page.route(`${MOCK_API_PREFIX}/expenditures*`, async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "exp-1",
            tower_id: TOWER_A.tower_id,
            expenditure_date: "2026-07-05",
            category: "other",
            description: "Complex-wide painting",
            vendor_payee_name: "XYZ Painters",
            amount: 80000,
            payment_mode: "cheque",
            attachment_s3_key: null,
            is_complex_contribution: true,
            complex_total_amount: 500000,
            recorded_by: "user-1",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            deactivated_at: null,
          },
        ],
        page: 1,
        page_size: 100,
        total: 1,
      }),
    });
  });

  await page.goto(`/towers/${TOWER_A.tower_id}/expenditures/new?type=complex-contribution`);

  // The trigger button's accessible name comes from its associated
  // <FormLabel> ("Date"), not its own "Pick a date" text content.
  await page.getByRole("button", { name: "Date", exact: true }).click();
  await page.locator("[data-day]").first().click();

  await page.getByLabel(/total complex expense amount/i).fill("500000");
  await page.getByLabel(/description/i).fill("Complex-wide painting");
  await page.getByLabel(/vendor\/payee name/i).fill("XYZ Painters");
  await page.getByLabel(/tower's share amount/i).fill("80000");

  await page.getByRole("combobox", { name: /payment mode/i }).click();
  await page.getByRole("option", { name: "Cheque" }).click();

  await page.getByRole("button", { name: "Record contribution" }).click();

  await expect(page).toHaveURL(new RegExp(`/towers/${TOWER_A.tower_id}/expenditures$`));
  expect(capturedBody).not.toBeNull();
  expect((capturedBody as unknown as { amount: number }).amount).toBe(80000);
  expect((capturedBody as unknown as { complex_total_amount: number }).complex_total_amount).toBe(500000);

  await expect(page.getByRole("cell", { name: "₹80,000.00" })).toBeVisible();
  await expect(page.getByTestId("category-totals")).toContainText("₹80,000.00");
  await expect(page.getByTestId("category-totals")).not.toContainText("500,000");
});
