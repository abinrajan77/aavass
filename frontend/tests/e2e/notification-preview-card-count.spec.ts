import { test, expect } from "@playwright/test";
import { ADMIN_SESSION, MOCK_API_PREFIX, TOWER_A, mockCommonListEndpoints, seedSessionCookie } from "../mocks/api";

/**
 * specs/05-reporting-owner-portal-notifications/frontend.md "Frontend Test
 * Plan": "admin opens the notification preview for a tenant-occupied flat's
 * overdue due — sees exactly 2 message cards (tenant, owner copy) in the
 * `AnimatedList`, each independently copyable; for an owner-occupied flat's
 * due, sees exactly 1 card."
 */
test("notification preview shows 2 cards for a tenant-occupied flat's due, 1 card for an owner-occupied flat's due", async ({
  page,
}) => {
  await mockCommonListEndpoints(page);
  await seedSessionCookie(page, ADMIN_SESSION);

  await page.route(`${MOCK_API_PREFIX}/notifications/templates/preview*`, async (route) => {
    const url = new URL(route.request().url());
    const dueId = url.searchParams.get("due_id");

    if (dueId === "due-tenant-occupied") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          event: "overdue_reminder",
          due_id: dueId,
          flat_number: "A-101",
          messages: [
            {
              recipient: "tenant",
              recipient_name: "Ravi Tenant",
              recipient_phone: "9000000001",
              message_text: "Dear Ravi, your maintenance due for A-101 is overdue.",
            },
            {
              recipient: "owner",
              recipient_name: "Priya Owner",
              recipient_phone: "9000000002",
              message_text: "Dear Priya, your tenant's maintenance due for A-101 is overdue.",
            },
          ],
        }),
      });
    }

    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        event: "overdue_reminder",
        due_id: dueId,
        flat_number: "B-202",
        messages: [
          {
            recipient: "owner",
            recipient_name: "Asha Owner",
            recipient_phone: "9000000003",
            message_text: "Dear Asha, your maintenance due for B-202 is overdue.",
          },
        ],
      }),
    });
  });

  await page.goto(
    `/towers/${TOWER_A.tower_id}/notifications/preview/due-tenant-occupied?event=overdue_reminder&due_type=maintenance`
  );
  await expect(page.getByTestId("notification-message-card")).toHaveCount(2);
  await expect(page.getByText("Ravi Tenant")).toBeVisible();
  await expect(page.getByText("Priya Owner")).toBeVisible();
  await expect(page.getByRole("button", { name: /send/i })).toHaveCount(0);

  await page.goto(
    `/towers/${TOWER_A.tower_id}/notifications/preview/due-owner-occupied?event=overdue_reminder&due_type=maintenance`
  );
  await expect(page.getByTestId("notification-message-card")).toHaveCount(1);
  await expect(page.getByText("Asha Owner")).toBeVisible();
  await expect(page.getByRole("button", { name: /send/i })).toHaveCount(0);
});
