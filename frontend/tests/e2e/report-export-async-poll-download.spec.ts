import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, TOWER_A, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";

/**
 * specs/05-reporting-owner-portal-notifications/frontend.md "Frontend Test
 * Plan": "admin triggers a CSV export that the backend resolves to >5000
 * rows — UI shows the 'Preparing export…' state, polls, and auto-downloads
 * the file once the job completes, without the admin needing to manually
 * refresh." Uses the Outstanding Dues tab (no billing-cycle dependency) —
 * backend.md §2.6's shared export flow: `202 { job_id }` beyond the sync
 * threshold, polled via the canonical `GET /towers/{tower_id}/jobs/{job_id}`
 * route (06-cloud-devops.md §4), `result.download_url` opened once `done`.
 */
test("a CSV export that resolves to an async job shows 'Preparing export…', polls, then auto-downloads", async ({
  page,
  context,
}) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.route(`${MOCK_API_PREFIX}/reports/outstanding-dues*`, async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("format")) {
      return route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ job_id: "export-job-1" }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tower_id: TOWER_A.tower_id,
        as_of_date: "2026-07-10",
        items: [],
        total_outstanding: 0,
      }),
    });
  });

  let jobPollCount = 0;
  await page.route(`${MOCK_API_PREFIX}/jobs/export-job-1`, async (route) => {
    jobPollCount += 1;
    if (jobPollCount < 2) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ job_id: "export-job-1", status: "pending" }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: "export-job-1",
        status: "done",
        result: { download_url: "http://localhost:3100/__mock_api__/fake-outstanding-dues.csv" },
      }),
    });
  });

  await page.route("**/fake-outstanding-dues.csv", (route) =>
    route.fulfill({ status: 200, contentType: "text/csv", body: "flat_number,amount_due\n" })
  );

  await page.goto(`/towers/${TOWER_A.tower_id}/reports?tab=outstanding_dues`);
  await expect(page.getByText("No overdue dues as of this date.")).toBeVisible();

  // Register the popup listener before clicking so it can't race past the
  // "done" transition (the job may resolve within a couple of poll cycles).
  const popupPromise = context.waitForEvent("page");
  await page.getByRole("button", { name: "Export CSV" }).click();

  // "Preparing export…" state shown while the job is in flight.
  await expect(page.getByText(/preparing csv export/i)).toBeVisible();

  const popup = await popupPromise;
  await popup.waitForLoadState();
  expect(popup.url()).toContain("fake-outstanding-dues.csv");

  await expect(page.getByText("Export ready")).toBeVisible();
  // Buttons return to their normal state once the job resolves — no
  // stuck "Preparing…" state left behind.
  await expect(page.getByRole("button", { name: "Export CSV" })).toBeVisible();
});
