import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";
import { MOCK_API_PREFIX } from "../mocks/api";
import {
  CYCLE_JULY_2026,
  DUE_OWNER_PENDING,
  DUE_TENANT_PENDING,
  TOWER_ID,
  mockBillingDashboardStats,
  mockCycleDetail,
} from "../mocks/billing";

/**
 * specs/03-maintenance-billing/frontend.md §4.2:
 * "Admin marks a due as Paid → the row's badge updates to 'Paid'/success
 * immediately (no full page reload needed) → a 'Download Receipt' link
 * appears on that row and successfully opens a PDF."
 */
test("marking a due paid updates its badge immediately and reveals Download Receipt", async ({ page, context }) => {
  await mockCommonListEndpoints(page);
  await mockCycleDetail(page);
  await mockBillingDashboardStats(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  let duesCallCount = 0;
  await page.route(`${MOCK_API_PREFIX}/billing-cycles/${CYCLE_JULY_2026.id}/dues*`, async (route) => {
    duesCallCount += 1;
    const due = duesCallCount === 1 ? DUE_OWNER_PENDING : { ...DUE_OWNER_PENDING, status: "paid" as const };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [due], page: 1, page_size: 100, total: 1 }),
    });
  });

  const receipt = {
    id: "receipt-1",
    receipt_number: "OAK-2026-000001",
    owner_name_snapshot: "Priya Owner",
    generated_at: "2026-07-09T10:00:00Z",
    download_url: "http://localhost:3100/__mock_api__/fake-receipt.pdf",
  };
  await page.route(`${MOCK_API_PREFIX}/dues/${DUE_OWNER_PENDING.id}/mark-paid`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ due: { ...DUE_OWNER_PENDING, status: "paid" }, receipt }),
    })
  );
  await page.route(`${MOCK_API_PREFIX}/dues/${DUE_OWNER_PENDING.id}/receipt`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ receipt_number: receipt.receipt_number, download_url: receipt.download_url }),
    })
  );
  await page.route("**/fake-receipt.pdf", (route) =>
    route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4 fake" })
  );

  await page.goto(`/towers/${TOWER_ID}/billing/cycles/${CYCLE_JULY_2026.id}`);
  const table = page.getByRole("table");
  await expect(table.getByText("Pending")).toBeVisible();

  await page.getByRole("button", { name: "Mark Paid" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Mark as paid" }).click();

  // Badge flips to Paid without a full page reload (TanStack Query invalidation refetch).
  await expect(table.getByText("Paid")).toBeVisible();
  const downloadReceiptButton = page.getByRole("button", { name: "Download Receipt" });
  await expect(downloadReceiptButton).toBeVisible();

  const [popup] = await Promise.all([context.waitForEvent("page"), downloadReceiptButton.click()]);
  await popup.waitForLoadState();
  expect(popup.url()).toContain("fake-receipt.pdf");
});

/**
 * specs/03-maintenance-billing/frontend.md §4.2: "A tenant-occupied flat's
 * due shows 'Assigned To: <tenant name> (tenant)' in the dues list."
 *
 * The second half of that scenario — "after marking it paid, the downloaded
 * receipt shows the primary owner's name, not the tenant's" — is a PDF
 * content assertion. Per frontend.md §2.4, receipts are always
 * server-rendered ("no client-side PDF rendering, always server-generated")
 * and opened via a pre-signed URL, so the frontend has no representation of
 * the owner name to assert against once the PDF is generated — that
 * guarantee is owned and already covered by the backend's own test plan
 * (backend.md §8.2: "Receipt for a due whose assigned_to_type='tenant'
 * still contains the flat's primary owner's name"). This test covers the
 * frontend-owned half: the dues list correctly displays the tenant
 * assignee before payment.
 */
test("a tenant-assigned due shows the tenant's name and a 'tenant' tag in the dues list", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await mockCycleDetail(page);
  await mockBillingDashboardStats(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.route(`${MOCK_API_PREFIX}/billing-cycles/${CYCLE_JULY_2026.id}/dues*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [DUE_TENANT_PENDING], page: 1, page_size: 100, total: 1 }),
    })
  );

  await page.goto(`/towers/${TOWER_ID}/billing/cycles/${CYCLE_JULY_2026.id}`);

  await expect(page.getByText("Ravi Tenant")).toBeVisible();
  await expect(page.getByText("tenant", { exact: true })).toBeVisible();
});
