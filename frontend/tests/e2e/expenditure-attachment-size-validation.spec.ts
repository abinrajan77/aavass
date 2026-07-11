import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, mockCommonListEndpoints, seedSessionCookie, TOWER_A } from "../mocks/api";

/**
 * frontend.md e2e test #5: "Uploading an expenditure attachment over the
 * size limit shows a validation error before submit." Attach a file >10 MB;
 * the inline field error appears immediately and no network call for the
 * presigned URL is made.
 */
test("oversized expenditure attachment is rejected client-side before any presigned-URL call", async ({ page }) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  let uploadUrlCalled = false;
  await page.route(`${MOCK_API_PREFIX}/expenditures/attachment-upload-url`, async (route) => {
    uploadUrlCalled = true;
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });

  await page.goto(`/towers/${TOWER_A.tower_id}/expenditures/new`);

  await page.setInputFiles('input[type="file"]', {
    name: "invoice.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.alloc(11 * 1024 * 1024, 1),
  });

  await expect(page.getByText(/file must be under 10 mb/i)).toBeVisible();

  await page.getByRole("button", { name: "Record expenditure" }).click();
  await expect(page.getByText(/file must be under 10 mb/i)).toBeVisible();
  expect(uploadUrlCalled).toBe(false);
});
